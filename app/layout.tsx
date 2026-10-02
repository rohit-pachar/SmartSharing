import type { Metadata } from 'next';
import './globals.css';
import './app.css';
import { AuthProvider } from './lib/auth';

const desc = 'Templates, LUTs, invoice kits and AI workflows for creators — instant download. Open your own storefront with discount codes, licence keys, analytics and integrations built in.';
export const metadata: Metadata = {
  metadataBase: new URL('https://smartsharing.in'),
  title: 'SmartSharing · Tools and assets for creators',
  description: desc,
  icons: { icon: '/favicon.svg', shortcut: '/favicon.svg' },
  openGraph: { type: 'website', siteName: 'SmartSharing', title: 'SmartSharing · Tools and assets for creators', description: desc, images: [{ url: '/art/prism.webp', width: 1536, height: 1024 }] },
  twitter: { card: 'summary_large_image', title: 'SmartSharing', description: desc, images: ['/art/prism.webp'] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
