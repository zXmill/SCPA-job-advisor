'use client';

import { CareerLoading } from '@/components/ui/career-loading';

export default function LoadingPage() {
  return (
    <CareerLoading
      fullScreen
      title="Menyiapkan SCPA"
      messages={[
        'Membaca sinyal profil',
        'Menyelaraskan model rekomendasi',
        'Menyiapkan ruang keputusan karier',
      ]}
    />
  );
}
