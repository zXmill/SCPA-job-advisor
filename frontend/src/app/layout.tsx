import type { Metadata, Viewport } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/lib/theme-context";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  weight: ["400", "500", "600", "700", "800", "900"],
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jakarta",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "SCPA — Smart Career Pathway Assistant | AI Career Intelligence for Indonesia",
  description:
    "The career path your skills are actually built for. SCPA matches Indonesian professionals to the right roles, surfaces skill gaps, and maps the road to your next title — powered by NCF, SBERT, and DQN.",
  keywords:
    "career, AI, Indonesia, job recommendation, career path, smart career advisor, skill gap analysis, salary intelligence",
};

export const viewport: Viewport = {
  themeColor: "#0A0F1E",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Pre-hydration script reads localStorage and sets data-theme synchronously
  // so the first paint already matches the user's chosen theme. Without this
  // there is a brief dark flash before ThemeProvider hydrates.
  const themeInitScript = `(function(){try{var stored=localStorage.getItem('scpa_theme');var system=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';var t=(stored==='light'||stored==='dark')?stored:system;document.documentElement.setAttribute('data-theme',t);document.documentElement.style.colorScheme=t;}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;

  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning className={`${inter.variable} ${jakarta.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="antialiased min-h-screen" style={{ backgroundColor: 'var(--bg-deep)', color: 'var(--text-primary)' }}>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
