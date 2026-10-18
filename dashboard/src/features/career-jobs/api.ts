import { api } from '@/lib/api/client';
import type { CareerCompany, CareerCompanyList, CareerJobPage } from '@/lib/api/types';

// Adding a company reads its careers site there and then.
const ADD_TIMEOUT_MS = 100_000;

export type CareerJobFilters = {
  /** Empty means every company. */
  companies: string[];
  places: string[];
  includeStretch: boolean;
};

export async function listCareerCompanies(): Promise<CareerCompanyList> {
  const { data } = await api.get<CareerCompanyList>('/career-jobs/companies');
  return data;
}

export async function addCareerCompany(link: string): Promise<CareerCompany> {
  const { data } = await api.post<CareerCompany>(
    '/career-jobs/companies',
    { link },
    { timeout: ADD_TIMEOUT_MS },
  );
  return data;
}

export async function listCareerJobs(
  filters: CareerJobFilters,
  cursor: string | null,
  limit = 20,
): Promise<CareerJobPage> {
  // Repeated keys (companies=a&companies=b), the way FastAPI reads a list.
  const params = new URLSearchParams();
  filters.companies.forEach((slug) => params.append('companies', slug));
  filters.places.forEach((place) => params.append('places', place));
  params.set('include_stretch', String(filters.includeStretch));
  params.set('limit', String(limit));
  if (cursor) params.set('cursor', cursor);
  const { data } = await api.get<CareerJobPage>('/career-jobs', { params });
  return data;
}
