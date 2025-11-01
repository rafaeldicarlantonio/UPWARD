/**
 * Hypotheses API Module
 * 
 * Client-side API functions for hypothesis management.
 */

// ============================================================================
// Types
// ============================================================================

export interface ProposeHypothesisRequest {
  /** Hypothesis title */
  title: string;
  
  /** Detailed description */
  description: string;
  
  /** Confidence score (0-1) */
  confidence_score: number;
  
  /** Optional message ID for context */
  message_id?: string;
  
  /** Optional tags */
  tags?: string[];
  
  /** Optional source references */
  sources?: string[];
}

export interface HypothesisData {
  /** Generated hypothesis ID */
  hypothesis_id: string;
  
  /** Hypothesis title */
  title: string;
  
  /** Description */
  description: string;
  
  /** Evaluated score */
  score: number;
  
  /** Whether it was persisted */
  persisted: boolean;
  
  /** Creation timestamp */
  created_at: string;
  
  /** User who created it */
  created_by?: string;
}

export interface ProposeHypothesisResponse {
  /** HTTP status code */
  status: 201 | 202;
  
  /** Response data */
  data: HypothesisData;
  
  /** Additional metadata */
  metadata?: {
    pareto_threshold?: number;
    evaluation_time_ms?: number;
  };
}

export interface HypothesisError {
  error: string;
  details?: string;
  status: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Propose a new hypothesis to the system.
 * 
 * @param request - Hypothesis proposal data
 * @param apiBaseUrl - Base URL for API (default: '/api')
 * @returns Response with status 201 (persisted) or 202 (not persisted)
 * @throws Error if request fails
 */
export async function proposeHypothesis(
  request: ProposeHypothesisRequest,
  apiBaseUrl: string = '/api'
): Promise<ProposeHypothesisResponse> {
  const url = `${apiBaseUrl}/hypotheses/propose`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    if (!response.ok) {
      // Handle error responses
      let errorMessage = `Request failed with status ${response.status}`;
      
      try {
        const errorData = await response.json();
        errorMessage = errorData.error || errorData.detail || errorMessage;
      } catch {
        // If JSON parsing fails, use status text
        errorMessage = response.statusText || errorMessage;
      }
      
      throw new Error(errorMessage);
    }
    
    const data = await response.json();
    
    return {
      status: response.status as 201 | 202,
      data: {
        hypothesis_id: data.hypothesis_id,
        title: data.title,
        description: data.description,
        score: data.score,
        persisted: response.status === 201,
        created_at: data.created_at || new Date().toISOString(),
        created_by: data.created_by,
      },
      metadata: {
        pareto_threshold: data.pareto_threshold,
        evaluation_time_ms: data.evaluation_time_ms,
      },
    };
  } catch (error) {
    console.error('Failed to propose hypothesis:', error);
    throw error;
  }
}

/**
 * Get a hypothesis by ID.
 * 
 * @param hypothesisId - Hypothesis ID
 * @param apiBaseUrl - Base URL for API
 * @returns Hypothesis data
 */
export async function getHypothesis(
  hypothesisId: string,
  apiBaseUrl: string = '/api'
): Promise<HypothesisData> {
  const url = `${apiBaseUrl}/hypotheses/${hypothesisId}`;
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get hypothesis: ${response.status}`);
  }
  
  return response.json();
}

/**
 * List hypotheses with optional filters.
 * 
 * @param filters - Query filters
 * @param apiBaseUrl - Base URL for API
 * @returns Array of hypotheses
 */
export async function listHypotheses(
  filters?: {
    persisted?: boolean;
    min_score?: number;
    limit?: number;
  },
  apiBaseUrl: string = '/api'
): Promise<HypothesisData[]> {
  const params = new URLSearchParams();
  
  if (filters?.persisted !== undefined) {
    params.set('persisted', String(filters.persisted));
  }
  if (filters?.min_score !== undefined) {
    params.set('min_score', String(filters.min_score));
  }
  if (filters?.limit !== undefined) {
    params.set('limit', String(filters.limit));
  }
  
  const url = `${apiBaseUrl}/hypotheses?${params.toString()}`;
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to list hypotheses: ${response.status}`);
  }
  
  const data = await response.json();
  return data.hypotheses || [];
}

export default {
  proposeHypothesis,
  getHypothesis,
  listHypotheses,
};
