'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navbar({ variant = 'light' }: { variant?: 'light' | 'dark' | 'app' }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const isApp = variant === 'app';

  return (
    <nav
      data-node-id="TopNavBar"
      className={`w-full z-50 sticky top-0 ${
        variant === 'dark' ? 'bg-[#3730A3]' : 'bg-white/80 backdrop-blur-md'
      } border-b border-[#00000014]`}
    >
      <div className="container-main flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#4F46E5] flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className={`font-bold text-xl ${variant === 'dark' ? 'text-white' : 'text-[#000000E6]'}`}>
            SCPA
          </span>
        </Link>

        {/* Desktop Nav Links */}
        {!isApp ? (
          <>
            <div className="hidden md:flex items-center gap-8">
              {['Home', 'Features', 'About'].map((item) => (
                <Link
                  key={item}
                  href={item === 'Home' ? '/' : `/#${item.toLowerCase()}`}
                  className={`text-sm font-medium transition-colors hover:text-[#4F46E5] pb-1 ${
                    variant === 'dark' ? 'text-white/70' : 'text-[#00000099]'
                  } ${item === 'Home' ? '!text-[#4F46E5] !font-semibold border-b-2 border-[#4F46E5]' : ''}`}
                >
                  {item}
                </Link>
              ))}
            </div>
            <div className="hidden md:flex items-center gap-3">
              <Link href="/auth" className="text-sm font-medium text-[#00000099] hover:text-[#4F46E5] transition-colors px-4 py-2">
                Login
              </Link>
              <Link href="/auth" className="btn-cta !py-2.5 !px-5 !text-sm inline-block no-underline">
                Mulai Sekarang
              </Link>
            </div>
          </>
        ) : (
          <>
            {/* App Navbar */}
            <div className="hidden md:flex items-center flex-1 mx-8">
              <div className="relative w-full max-w-md">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#00000066]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search..."
                  className="input-field !pl-10 !py-2 !text-sm !bg-[#F5F5F5]"
                />
              </div>
            </div>
            <div className="hidden md:flex items-center gap-6 text-sm">
              {[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Vacancies', href: '/analytics' },
                { label: 'Recommendations', href: '/recommendations' },
                { label: 'My Applications', href: '/apply' },
              ].map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`transition-colors font-medium pb-1 ${pathname === item.href ? 'text-[#4F46E5] border-b-2 border-[#4F46E5]' : 'text-[#00000099] hover:text-[#4F46E5]'}`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
            <div className="hidden md:flex items-center gap-3 ml-6">
              <button className="w-8 h-8 rounded-full bg-[#F5F5F5] flex items-center justify-center text-[#00000099] hover:text-[#4F46E5] transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </button>
              <Link href="/profile" className="w-8 h-8 rounded-full bg-[#4F46E5] flex items-center justify-center text-white text-xs font-bold">
                BS
              </Link>
            </div>
          </>
        )}

        {/* Mobile Hamburger */}
        <button
          className="md:hidden p-2"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="md:hidden bg-white border-t border-[#00000014] animate-slide-up">
          <div className="p-4 flex flex-col gap-3">
            {!isApp ? (
              <>
                {['Home', 'Features', 'About'].map((item) => (
                  <Link key={item} href={item === 'Home' ? '/' : `/#${item.toLowerCase()}`} className={`py-2 font-medium ${item === 'Home' ? 'text-[#4F46E5] border-b-2 border-[#4F46E5]' : 'text-[#00000099]'}`}>
                    {item}
                  </Link>
                ))}
                <hr className="border-[#00000014]" />
                <Link href="/auth" className="text-[#00000099] py-2 font-medium">Login</Link>
                <Link href="/auth" className="btn-cta text-center !py-2.5">Mulai Sekarang</Link>
              </>
            ) : (
              <>
                {[
                  { label: 'Dashboard', href: '/dashboard' },
                  { label: 'Vacancies', href: '/analytics' },
                  { label: 'Recommendations', href: '/recommendations' },
                  { label: 'My Applications', href: '/apply' },
                ].map((item) => (
                  <Link key={item.label} href={item.href} className={`py-2 font-medium ${pathname === item.href ? 'text-[#4F46E5] border-b-2 border-[#4F46E5]' : 'text-[#00000099]'}`}>
                    {item.label}
                  </Link>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
