export const SUPPLIER_COUNTRIES = ['Spain', 'USA'] as const;
export const SUPPLIER_CURRENCIES = ['EUR', 'USD'] as const;
export const SUPPLIER_STATUSES = ['active', 'suspended'] as const;
export const SUPPLIER_CATEGORIES = [
  'job_boards',
  'ats_software',
  'assessment_tools',
  'training_platforms',
  'payroll_and_hr_software',
  'video_interview',
  'background_check',
  'office_and_facilities',
  'it_and_software_licenses',
] as const;

export type SupplierCountry = (typeof SUPPLIER_COUNTRIES)[number];
export type SupplierCurrency = (typeof SUPPLIER_CURRENCIES)[number];
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number];
export type SupplierCategory = (typeof SUPPLIER_CATEGORIES)[number];

export type Supplier = {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: SupplierCurrency;
  status: SupplierStatus;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
  updated_at: string;
};

export type SupplierInput = {
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: SupplierCurrency;
  status: SupplierStatus;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
};

export const SUPPLIER_STATUS_LABELS: Record<SupplierStatus, string> = {
  active: 'Activo',
  suspended: 'Suspendido',
};

export const SUPPLIER_CATEGORY_LABELS: Record<SupplierCategory, string> = {
  job_boards: 'Bolsas de empleo',
  ats_software: 'Software ATS',
  assessment_tools: 'Herramientas de evaluacion',
  training_platforms: 'Plataformas de formacion',
  payroll_and_hr_software: 'Nomina y software RRHH',
  video_interview: 'Entrevista por video',
  background_check: 'Verificacion de antecedentes',
  office_and_facilities: 'Oficina e instalaciones',
  it_and_software_licenses: 'Licencias IT y software',
};

export const SUPPLIER_COUNTRY_LABELS: Record<SupplierCountry, string> = {
  Spain: 'Espana',
  USA: 'Estados Unidos',
};
