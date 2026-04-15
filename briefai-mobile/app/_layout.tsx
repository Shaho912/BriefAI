import { useEffect, useState } from 'react';
import { Slot, useRouter, useSegments } from 'expo-router';
import { Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { apiFetch } from '../lib/api';

export default function RootLayout() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session === undefined) return; // still loading

    if (!session) {
      setHasProfile(null);
      router.replace('/(auth)/welcome');
      return;
    }

    // Check if the user has completed onboarding (has a profile)
    apiFetch<{ focus_text: string }>('/settings')
      .then(() => setHasProfile(true))
      .catch(async (err: Error) => {
        // If the backend rejects the token (user deleted), sign out to clear local session
        if (err.message.includes('401') || err.message.includes('Unauthorized') || err.message.includes('not found')) {
          await supabase.auth.signOut();
        } else {
          setHasProfile(false);
        }
      });
  }, [session]);

  useEffect(() => {
    if (session === undefined || hasProfile === null) return;

    const inAuth = segments[0] === '(auth)';
    const inTabs = segments[0] === '(tabs)';

    if (!session && !inAuth) {
      router.replace('/(auth)/welcome');
    } else if (session && hasProfile === false && segments[1] !== 'onboarding') {
      router.replace('/(auth)/onboarding');
    } else if (session && hasProfile === true && inAuth) {
      router.replace('/(tabs)/today');
    }
  }, [session, hasProfile, segments]);

  return <Slot />;
}
