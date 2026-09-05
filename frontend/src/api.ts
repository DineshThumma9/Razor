import { z } from 'zod'
import { CaseSchema, StatsSchema, type Case, type Stats } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

// Generic helper: parse + validate response with a Zod schema
async function get<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const data = await request<unknown>(path)
  return schema.parse(data)
}

export async function fetchCases(): Promise<Case[]> {
  return get('/cases', z.array(CaseSchema))
}

export async function fetchCase(caseId: string): Promise<Case> {
  return get(`/cases/${caseId}`, CaseSchema)
}

export async function fetchStats(): Promise<Stats> {
  return get('/metrics', StatsSchema)
}

export async function approveEscalation(caseId: string): Promise<void> {
  await request(`/cases/${caseId}/approve`, { method: 'POST' })
}

export async function closeCase(caseId: string): Promise<void> {
  await request(`/cases/${caseId}/close`, { method: 'POST' })
}

export async function simulateFire(payload: any): Promise<{ id: string }> {
  return request<{ id: string }>('/fake-event', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function simulateAction(payload: any): Promise<any> {
  return request('/fake-action', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function clearAllCases(): Promise<void> {
  await request('/cases/clear', { method: 'DELETE' })
}