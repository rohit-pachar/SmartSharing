import { Suspense } from 'react';
import { AuthScreen } from '../auth-screen';

export const metadata = { title: 'Log in · SmartSharing' };
export default function Page() { return <Suspense><AuthScreen mode="login" /></Suspense> }
