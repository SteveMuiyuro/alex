// API configuration that works for both local and production environments
export const getApiUrl = () => {
  // In production (static export), use relative path routed by hosting layer to the API service
  // In development, use localhost:8000
  if (typeof window !== 'undefined') {
    // Client-side: check if we're on localhost
    if (window.location.hostname === 'localhost') {
      return 'http://localhost:8000';
    } else {
      // Production: use relative path (/api/* routed by hosting layer)
      return '';
    }
  }
  // Server-side during build
  return '';
};

export const API_URL = getApiUrl();
