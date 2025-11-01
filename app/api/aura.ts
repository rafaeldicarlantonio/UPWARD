/**
 * AURA API Module
 * 
 * Client-side API functions for AURA project management.
 */

// ============================================================================
// Types
// ============================================================================

export interface ProposeAuraProjectRequest {
  /** Project title */
  title: string;
  
  /** Project description */
  description: string;
  
  /** Linked hypothesis ID */
  hypothesis_id: string;
  
  /** Starter tasks (1-3) */
  starter_tasks?: string[];
  
  /** Optional message ID for context */
  message_id?: string;
  
  /** Optional tags */
  tags?: string[];
}

export interface AuraProjectData {
  /** Generated project ID */
  project_id: string;
  
  /** Project title */
  title: string;
  
  /** Description */
  description: string;
  
  /** Linked hypothesis ID */
  hypothesis_id: string;
  
  /** Created starter tasks */
  starter_tasks?: Array<{
    task_id: string;
    title: string;
    status: string;
  }>;
  
  /** Creation timestamp */
  created_at: string;
  
  /** User who created it */
  created_by?: string;
}

export interface ProposeAuraProjectResponse {
  /** Response data */
  data: AuraProjectData;
  
  /** Additional metadata */
  metadata?: {
    evaluation_time_ms?: number;
  };
}

export interface HypothesisSummary {
  /** Hypothesis ID */
  hypothesis_id: string;
  
  /** Hypothesis title */
  title: string;
  
  /** Score */
  score: number;
  
  /** Creation timestamp */
  created_at: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Propose a new AURA project.
 * 
 * @param request - Project proposal data
 * @param apiBaseUrl - Base URL for API (default: '/api')
 * @returns Response with project data
 * @throws Error if request fails
 */
export async function proposeAuraProject(
  request: ProposeAuraProjectRequest,
  apiBaseUrl: string = '/api'
): Promise<ProposeAuraProjectResponse> {
  const url = `${apiBaseUrl}/aura/projects/propose`;
  
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
      data: {
        project_id: data.project_id,
        title: data.title,
        description: data.description,
        hypothesis_id: data.hypothesis_id,
        starter_tasks: data.starter_tasks || [],
        created_at: data.created_at || new Date().toISOString(),
        created_by: data.created_by,
      },
      metadata: {
        evaluation_time_ms: data.evaluation_time_ms,
      },
    };
  } catch (error) {
    console.error('Failed to propose AURA project:', error);
    throw error;
  }
}

/**
 * Get an AURA project by ID.
 * 
 * @param projectId - Project ID
 * @param apiBaseUrl - Base URL for API
 * @returns Project data
 */
export async function getAuraProject(
  projectId: string,
  apiBaseUrl: string = '/api'
): Promise<AuraProjectData> {
  const url = `${apiBaseUrl}/aura/projects/${projectId}`;
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get project: ${response.status}`);
  }
  
  return response.json();
}

/**
 * List AURA projects with optional filters.
 * 
 * @param filters - Query filters
 * @param apiBaseUrl - Base URL for API
 * @returns Array of projects
 */
export async function listAuraProjects(
  filters?: {
    hypothesis_id?: string;
    status?: string;
    limit?: number;
  },
  apiBaseUrl: string = '/api'
): Promise<AuraProjectData[]> {
  const params = new URLSearchParams();
  
  if (filters?.hypothesis_id) {
    params.set('hypothesis_id', filters.hypothesis_id);
  }
  if (filters?.status) {
    params.set('status', filters.status);
  }
  if (filters?.limit !== undefined) {
    params.set('limit', String(filters.limit));
  }
  
  const url = `${apiBaseUrl}/aura/projects?${params.toString()}`;
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to list projects: ${response.status}`);
  }
  
  const data = await response.json();
  return data.projects || [];
}

/**
 * List recent hypotheses for selection.
 * 
 * @param filters - Query filters
 * @param apiBaseUrl - Base URL for API
 * @returns Array of hypothesis summaries
 */
export async function listRecentHypotheses(
  filters?: {
    limit?: number;
    persisted_only?: boolean;
  },
  apiBaseUrl: string = '/api'
): Promise<HypothesisSummary[]> {
  const params = new URLSearchParams();
  
  if (filters?.limit !== undefined) {
    params.set('limit', String(filters.limit));
  }
  if (filters?.persisted_only !== undefined) {
    params.set('persisted', String(filters.persisted_only));
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
  const hypotheses = data.hypotheses || [];
  
  // Map to summary format
  return hypotheses.map((h: any) => ({
    hypothesis_id: h.hypothesis_id,
    title: h.title,
    score: h.score,
    created_at: h.created_at,
  }));
}

export default {
  proposeAuraProject,
  getAuraProject,
  listAuraProjects,
  listRecentHypotheses,
};
