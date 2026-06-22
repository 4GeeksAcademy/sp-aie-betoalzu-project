export type ApplicationFormData = {
  fullName: string;
  jobTitle: string;
  workEmail: string;
  phone: string;
  companyName: string;
  companyWebsite: string;
  industry: string;
  companySize: string;
  services: string[];
  priorityArea: string;
  budget: string;
  timeline: string;
  projectDetails: string;
  privacyConsent: boolean;
  newsletter: boolean;
};

export type ApplicationFormErrors = Partial<Record<keyof ApplicationFormData | "services", string>>;

export const initialFormData: ApplicationFormData = {
  fullName: "",
  jobTitle: "",
  workEmail: "",
  phone: "",
  companyName: "",
  companyWebsite: "",
  industry: "",
  companySize: "",
  services: [],
  priorityArea: "",
  budget: "",
  timeline: "",
  projectDetails: "",
  privacyConsent: false,
  newsletter: false,
};
