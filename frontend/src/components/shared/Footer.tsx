'use client';

import React from 'react';
import Link from 'next/link';

export default function Footer() {
  return (
    <footer data-node-id="Footer" className="bg-white border-t border-[#00000014] py-8">
      <div className="container-main flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Logo + Copyright */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-[#00000099] flex items-center justify-center" aria-hidden="true">
            <span className="text-white font-bold text-xs">S</span>
          </div>
          <div>
            <span className="font-bold text-sm text-[#000000E6]">SCPA</span>
            <span className="text-xs text-[#00000066] ml-2">Indonesian Career Intelligence</span>
          </div>
        </div>

        <p className="text-xs text-[#00000066]">
          © {new Date().getFullYear()} SCPA. Indonesian Career Intelligence.
        </p>

        {/* Links */}
        <div className="flex items-center gap-6">
          {['About', 'Help', 'Contact', 'Partner Portals'].map((item) => (
            <Link
              key={item}
              href="#"
              className="text-xs text-[#00000066] hover:text-[#4F46E5] transition-colors font-medium"
            >
              {item}
            </Link>
          ))}
        </div>
      </div>
    </footer>
  );
}
