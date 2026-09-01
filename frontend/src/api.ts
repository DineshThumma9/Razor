import axios from 'axios'
import { z } from 'zod'
import { CaseSchema, StatsSchema, type Case, type Stats } from './types'

const http = axios.create({
  baseURL: import.meta.env.API_URL || import.meta.env.VITE_API_URL,
  timeout: 15000,
})

// Generic helper: parse + validate response with a Zod schema
async function get<T>(url: string, schema: z.ZodType<T>): Promise<T> {
  const { data } = await http.get(url)
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
  await http.post(`/cases/${caseId}/approve`)
}

export async function closeCase(caseId: string): Promise<void> {
  await http.post(`/cases/${caseId}/close`)
}
