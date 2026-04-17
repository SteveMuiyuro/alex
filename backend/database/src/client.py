"""
PostgreSQL Client Wrapper (GCP Cloud SQL compatible)
Provides a simple interface for database operations while preserving
existing DataAPIClient method signatures used across the codebase.
"""

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
import uuid

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass  # dotenv not installed, continue without it

logger = logging.getLogger(__name__)


class DataAPIClient:
    """
    Compatibility wrapper that keeps the legacy DataAPIClient interface,
    but executes directly against PostgreSQL using SQLAlchemy.
    """

    def __init__(
        self,
        cluster_arn: str = None,
        secret_arn: str = None,
        database: str = None,
        region: str = None,
    ):
        """
        Initialize PostgreSQL client.

        NOTE: Signature intentionally unchanged for compatibility.
        Unused legacy args (cluster_arn, secret_arn, region) are accepted.

        Env vars (preferred):
            DATABASE_URL
        or
            DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
        """
        # Keep legacy attributes to avoid breaking external callers.
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.region = region

        self.database = database or os.environ.get("DB_NAME", "alex")

        self.database_url = os.environ.get("DATABASE_URL") or self._build_database_url(self.database)
        if not self.database_url:
            raise ValueError(
                "Missing required PostgreSQL configuration. "
                "Set DATABASE_URL or DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME."
            )

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            poolclass=NullPool,
        )

        self._transactions: Dict[str, tuple[Connection, Any]] = {}

    def execute(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """
        Execute SQL statement.

        Returns a Data-API-like response dict for backward compatibility:
        {
          "records": [...],
          "columnMetadata": [{"name": ...}],
          "numberOfRecordsUpdated": int
        }
        """
        bind_params = self._normalize_parameters(parameters)

        try:
            with self.engine.begin() as conn:
                result = conn.execute(text(sql), bind_params)

                if result.returns_rows:
                    rows = result.fetchall()
                    column_names = list(result.keys())
                    return {
                        "records": [self._row_to_data_api_record(row) for row in rows],
                        "columnMetadata": [{"name": col} for col in column_names],
                        "numberOfRecordsUpdated": result.rowcount if result.rowcount != -1 else 0,
                    }

                return {
                    "records": [],
                    "columnMetadata": [],
                    "numberOfRecordsUpdated": result.rowcount if result.rowcount != -1 else 0,
                }

        except SQLAlchemyError as e:
            logger.error("Database error: %s", e)
            raise

    def query(self, sql: str, parameters: List[Dict] = None) -> List[Dict]:
        """Execute a SELECT query and return results as list of dicts."""
        response = self.execute(sql, parameters)
        if "records" not in response:
            return []

        columns = [col["name"] for col in response.get("columnMetadata", [])]

        results: List[Dict] = []
        for record in response["records"]:
            row: Dict[str, Any] = {}
            for i, col in enumerate(columns):
                row[col] = self._extract_value(record[i])
            results.append(row)

        return results

    def query_one(self, sql: str, parameters: List[Dict] = None) -> Optional[Dict]:
        """Execute a SELECT query and return first result."""
        results = self.query(sql, parameters)
        return results[0] if results else None

    def insert(self, table: str, data: Dict, returning: str = None) -> str:
        """Insert a record into a table."""
        columns = list(data.keys())
        placeholders = []

        for col in columns:
            if isinstance(data[col], (dict, list)):
                placeholders.append(f":{col}::jsonb")
            elif isinstance(data[col], Decimal):
                placeholders.append(f":{col}::numeric")
            elif isinstance(data[col], date) and not isinstance(data[col], datetime):
                placeholders.append(f":{col}::date")
            elif isinstance(data[col], datetime):
                placeholders.append(f":{col}::timestamp")
            else:
                placeholders.append(f":{col}")

        sql = f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
        """

        if returning:
            sql += f" RETURNING {returning}"

        parameters = self._build_parameters(data)
        response = self.execute(sql, parameters)

        if returning and response.get("records"):
            return self._extract_value(response["records"][0][0])
        return None

    def update(self, table: str, data: Dict, where: str, where_params: Dict = None) -> int:
        """Update records in a table."""
        set_parts = []
        for col, val in data.items():
            if isinstance(val, (dict, list)):
                set_parts.append(f"{col} = :{col}::jsonb")
            elif isinstance(val, Decimal):
                set_parts.append(f"{col} = :{col}::numeric")
            elif isinstance(val, date) and not isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::date")
            elif isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::timestamp")
            else:
                set_parts.append(f"{col} = :{col}")

        set_clause = ", ".join(set_parts)

        sql = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {where}
        """

        all_params = {**data, **(where_params or {})}
        parameters = self._build_parameters(all_params)

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def delete(self, table: str, where: str, where_params: Dict = None) -> int:
        """Delete records from a table."""
        sql = f"DELETE FROM {table} WHERE {where}"
        parameters = self._build_parameters(where_params) if where_params else None

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def begin_transaction(self) -> str:
        """Begin a database transaction and return a transaction ID."""
        tx_id = str(uuid.uuid4())
        conn = self.engine.connect()
        tx = conn.begin()
        self._transactions[tx_id] = (conn, tx)
        return tx_id

    def commit_transaction(self, transaction_id: str):
        """Commit a database transaction."""
        conn, tx = self._transactions.pop(transaction_id)
        try:
            tx.commit()
        finally:
            conn.close()

    def rollback_transaction(self, transaction_id: str):
        """Rollback a database transaction."""
        conn, tx = self._transactions.pop(transaction_id)
        try:
            tx.rollback()
        finally:
            conn.close()

    def _build_parameters(self, data: Dict) -> List[Dict]:
        """Convert dictionary to legacy parameter format."""
        if not data:
            return []

        parameters = []
        for key, value in data.items():
            param = {"name": key}

            if value is None:
                param["value"] = {"isNull": True}
            elif isinstance(value, bool):
                param["value"] = {"booleanValue": value}
            elif isinstance(value, int):
                param["value"] = {"longValue": value}
            elif isinstance(value, float):
                param["value"] = {"doubleValue": value}
            elif isinstance(value, Decimal):
                param["value"] = {"stringValue": str(value)}
            elif isinstance(value, (date, datetime)):
                param["value"] = {"stringValue": value.isoformat()}
            elif isinstance(value, dict):
                param["value"] = {"stringValue": json.dumps(value)}
            elif isinstance(value, list):
                param["value"] = {"stringValue": json.dumps(value)}
            else:
                param["value"] = {"stringValue": str(value)}

            parameters.append(param)

        return parameters

    def _extract_value(self, field: Dict) -> Any:
        """Extract value from Data-API-like field response."""
        if field.get("isNull"):
            return None
        if "booleanValue" in field:
            return field["booleanValue"]
        if "longValue" in field:
            return field["longValue"]
        if "doubleValue" in field:
            return field["doubleValue"]
        if "stringValue" in field:
            value = field["stringValue"]
            if value and isinstance(value, str) and value[0] in ["{", "["]:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        if "blobValue" in field:
            return field["blobValue"]
        return None

    def _build_database_url(self, database: str) -> Optional[str]:
        """Build DATABASE_URL from DB_* environment vars if provided."""
        user = os.environ.get("DB_USER")
        password = os.environ.get("DB_PASSWORD")
        host = os.environ.get("DB_HOST")
        port = os.environ.get("DB_PORT", "5432")
        dbname = database or os.environ.get("DB_NAME")

        if not user or password is None or not host or not dbname:
            return None

        return f"postgresql+psycopg2://{user}:{quote_plus(password)}@{host}:{port}/{dbname}"

    def _normalize_parameters(self, parameters: Optional[List[Dict]]) -> Dict[str, Any]:
        """Convert legacy Data API parameters list into SQLAlchemy bind param dict."""
        if not parameters:
            return {}

        normalized: Dict[str, Any] = {}
        for param in parameters:
            name = param.get("name")
            if not name:
                continue
            value_obj = param.get("value", {})
            normalized[name] = self._from_data_api_value(value_obj)
        return normalized

    def _from_data_api_value(self, value_obj: Dict[str, Any]) -> Any:
        """Convert a legacy Data API value object to a Python value."""
        if value_obj.get("isNull"):
            return None
        if "booleanValue" in value_obj:
            return value_obj["booleanValue"]
        if "longValue" in value_obj:
            return value_obj["longValue"]
        if "doubleValue" in value_obj:
            return value_obj["doubleValue"]
        if "stringValue" in value_obj:
            raw = value_obj["stringValue"]
            if isinstance(raw, str) and raw and raw[0] in ["{", "["]:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return raw
            return raw
        if "blobValue" in value_obj:
            return value_obj["blobValue"]
        return None

    def _row_to_data_api_record(self, row: Any) -> List[Dict[str, Any]]:
        """Convert SQLAlchemy Row to legacy Data API record format."""
        record: List[Dict[str, Any]] = []
        for value in row:
            record.append(self._to_data_api_field(value))
        return record

    def _to_data_api_field(self, value: Any) -> Dict[str, Any]:
        """Convert Python/DB value to legacy Data API field format."""
        if value is None:
            return {"isNull": True}
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int):
            return {"longValue": value}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, Decimal):
            return {"stringValue": str(value)}
        if isinstance(value, datetime):
            return {"stringValue": value.isoformat()}
        if isinstance(value, date):
            return {"stringValue": value.isoformat()}
        if isinstance(value, (dict, list)):
            return {"stringValue": json.dumps(value)}
        return {"stringValue": str(value)}
