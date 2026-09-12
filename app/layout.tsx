import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'SmartSharing | The creator-to-creator exchange',description:'Explore a new way to license creative assets and tested AI workflows directly from creators. A researched marketplace concept for smartsharing.in.',icons:{icon:'/favicon.svg',shortcut:'/favicon.svg'}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><body>{children}</body></html>}
