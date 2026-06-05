// Shared types for SCPA platform

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  type: string; // Full-time, Contract, etc.
  salary?: string;
  matchScore: number;
  tags: string[];
  description: string;
  postedDate: string;
  source: string;
  logoUrl?: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  programStudi: string;
  university: string;
  skills: string[];
  certifications: string[];
  interests: string[];
  completionPercent: number;
}

export interface Recommendation {
  job: Job;
  ncfScore: number;
  sbertScore: number;
  dqnScore: number;
  hybridScore: number;
  matchLevel: 'HIGH' | 'MEDIUM' | 'LOW';
  reasons: string[];
}

export interface OnboardingStep {
  id: number;
  title: string;
  titleEn: string;
  completed: boolean;
}

export interface Application {
  id: string;
  job: Job;
  status: 'APPLYING' | 'SUBMITTED' | 'REVIEWED' | 'ACCEPTED' | 'REJECTED';
  appliedDate: string;
}

export interface NewsItem {
  id: string;
  title: string;
  category: string;
  date: string;
  imageUrl?: string;
  summary: string;
}

export interface MetricCard {
  label: string;
  value: string | number;
  change?: number;
  unit?: string;
}
