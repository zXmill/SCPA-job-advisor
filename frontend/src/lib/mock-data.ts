// Mock data for SCPA platform

import { Job, UserProfile, Recommendation, NewsItem, Application } from './types';

export const mockUser: UserProfile = {
  id: 'user-001',
  name: 'Budi Santoso',
  email: 'budi@example.com',
  programStudi: 'Teknik Informatika',
  university: 'Universitas Indonesia',
  skills: ['Python', 'Machine Learning', 'Data Analysis', 'SQL', 'React'],
  certifications: ['Google Data Analytics', 'AWS Cloud Practitioner'],
  interests: ['AI/ML', 'Data Science', 'Cloud Computing'],
  completionPercent: 85,
};

export const mockJobs: Job[] = [
  {
    id: 'job-001',
    title: 'Data Scientist Junior',
    company: 'PT Tokopedia',
    location: 'Jakarta, Indonesia',
    type: 'Full-time',
    salary: 'Rp 12-18 juta/bulan',
    matchScore: 94,
    tags: ['Python', 'SQL', 'Machine Learning'],
    description: 'Bergabung dengan tim data science kami untuk mengembangkan model prediktif dan analisis data.',
    postedDate: '2 hari lalu',
    source: 'JobStreet',
  },
  {
    id: 'job-002',
    title: 'Product Manager',
    company: 'Gojek',
    location: 'Jakarta, Indonesia',
    type: 'Full-time',
    salary: 'Rp 15-25 juta/bulan',
    matchScore: 87,
    tags: ['Agile', 'Sprint', 'Analytics'],
    description: 'Memimpin pengembangan produk digital untuk jutaan pengguna di Asia Tenggara.',
    postedDate: '1 hari lalu',
    source: 'LinkedIn',
  },
  {
    id: 'job-003',
    title: 'Frontend Engineer',
    company: 'Bukalapak',
    location: 'Jakarta, Indonesia',
    type: 'Full-time',
    salary: 'Rp 10-16 juta/bulan',
    matchScore: 89,
    tags: ['React', 'TypeScript', 'Next.js'],
    description: 'Membangun antarmuka pengguna yang responsif dan performant.',
    postedDate: '3 hari lalu',
    source: 'Glints',
  },
  {
    id: 'job-004',
    title: 'Senior Data Analyst',
    company: 'Gopay Indonesia',
    location: 'Jakarta, Indonesia',
    type: 'Full-time',
    salary: 'Rp 18-28 juta/bulan',
    matchScore: 91,
    tags: ['SQL', 'Tableau', 'Python'],
    description: 'Menganalisis data bisnis untuk mendukung pengambilan keputusan strategis.',
    postedDate: '1 hari lalu',
    source: 'JobStreet',
  },
  {
    id: 'job-005',
    title: 'Business Intelligence Specialist',
    company: 'Tokopedia',
    location: 'Jakarta, Indonesia',
    type: 'Contract',
    matchScore: 76,
    tags: ['BI Tools', 'SQL', 'Data Visualization'],
    description: 'Membangun dashboard dan laporan analitik untuk stakeholder bisnis.',
    postedDate: '5 hari lalu',
    source: 'LinkedIn',
  },
  {
    id: 'job-006',
    title: 'UX/UI Designer',
    company: 'Traveloka',
    location: 'Jakarta, Indonesia',
    type: 'Full-time',
    salary: 'Rp 12-20 juta/bulan',
    matchScore: 72,
    tags: ['Figma', 'User Research', 'Prototyping'],
    description: 'Merancang pengalaman pengguna yang intuitif untuk platform travel.',
    postedDate: '2 hari lalu',
    source: 'Glints',
  },
];

export const mockRecommendations: Recommendation[] = [
  {
    job: mockJobs[0],
    ncfScore: 0.91,
    sbertScore: 0.96,
    dqnScore: 0.88,
    hybridScore: 0.94,
    matchLevel: 'HIGH',
    reasons: [
      'Keahlian Python dan ML Anda sangat cocok',
      'Pengalaman data analysis relevan dengan posisi ini',
      'Lokasi sesuai preferensi Anda',
    ],
  },
  {
    job: mockJobs[3],
    ncfScore: 0.88,
    sbertScore: 0.93,
    dqnScore: 0.85,
    hybridScore: 0.91,
    matchLevel: 'HIGH',
    reasons: [
      'Skill SQL dan analitik data cocok',
      'Sertifikasi Google Data Analytics relevan',
      'Perusahaan fintech sesuai minat Anda',
    ],
  },
  {
    job: mockJobs[2],
    ncfScore: 0.85,
    sbertScore: 0.92,
    dqnScore: 0.82,
    hybridScore: 0.89,
    matchLevel: 'HIGH',
    reasons: [
      'Kemampuan React dan TypeScript cocok',
      'Pengalaman frontend development relevan',
    ],
  },
  {
    job: mockJobs[1],
    ncfScore: 0.82,
    sbertScore: 0.89,
    dqnScore: 0.80,
    hybridScore: 0.87,
    matchLevel: 'MEDIUM',
    reasons: [
      'Background teknis mendukung peran PM',
      'Pengalaman analitik data relevan',
    ],
  },
  {
    job: mockJobs[4],
    ncfScore: 0.70,
    sbertScore: 0.80,
    dqnScore: 0.72,
    hybridScore: 0.76,
    matchLevel: 'MEDIUM',
    reasons: [
      'Skill SQL cocok untuk posisi BI',
      'Pengalaman data visualization mendukung',
    ],
  },
];

export const mockNews: NewsItem[] = [
  {
    id: 'news-001',
    title: 'Permintaan Talent AI Meningkat 300% di Jakarta',
    category: 'Tech',
    date: '3 days ago',
    summary: 'Lonjak besar dalam pencarian profesional AI mendorong perusahaan teknologi terkemuka membuka lebih dari 500 posisi baru di bidang kecerdasan buatan.',
  },
  {
    id: 'news-002',
    title: '5 Strategi Menjawab Pertanyaan Wawancara Sulit',
    category: 'Tips',
    date: '5 days ago',
    summary: 'Panduan bagi profesional untuk menghadapi wawancara kerja dengan percaya diri dan tampil menonjol dari kandidat lainnya.',
  },
  {
    id: 'news-003',
    title: 'Startup Indonesia Raih Pendanaan Seri B $50M',
    category: 'Funding',
    date: '1 day ago',
    summary: 'Startup edtech lokal mendapat investasi besar untuk ekspansi platform pembelajaran digital ke seluruh Asia Tenggara.',
  },
];

export const mockApplications: Application[] = [
  {
    id: 'app-001',
    job: mockJobs[0],
    status: 'SUBMITTED',
    appliedDate: '2024-01-15',
  },
  {
    id: 'app-002',
    job: mockJobs[2],
    status: 'REVIEWED',
    appliedDate: '2024-01-14',
  },
];

export const partnerLogos = [
  { name: 'JobPortal ID', icon: '🏢' },
  { name: 'ProConnect', icon: '🤝' },
  { name: 'IndoKarier', icon: '🇮🇩' },
];

export const trendingSkills = [
  'Data Analysis',
  'Digital Marketing',
  'Cloud Computing',
  'UI/UX Design',
  'Cybersecurity',
];
