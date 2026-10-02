import { Suspense } from 'react';
import { AuthScreen } from '../auth-screen';

export const metadata = { title: 'Create your account · SmartSharing' };
export default function Page() { return <Suspense><AuthScreen mode="signup" /></Suspense> }
