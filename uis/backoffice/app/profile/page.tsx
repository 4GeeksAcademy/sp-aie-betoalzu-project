'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Redirect from /profile to /account/profile
 * (backwards compatibility)
 */
export default function ProfilePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/account/profile');
  }, [router]);

  return (
    <main className="mx-auto flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <p className="text-sm text-slate-400">Redirigiendo...</p>
    </main>
  );
}
