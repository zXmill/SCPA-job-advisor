'use client';

import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#F5F5F5] flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-[#000000E6] text-xl font-bold mb-2">404</h1>
        <p className="text-[#00000099] text-base mb-4">Halaman tidak ditemukan</p>
        <p className="text-sm text-[#00000066] mb-8">The page you are looking for does not exist.</p>
        <Link href="/" className="btn-cta inline-flex items-center gap-2">
          Kembali ke Beranda
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </Link>
      </div>
    </div>
  );
}