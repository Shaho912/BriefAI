import { useEffect } from 'react';
import { Redirect } from 'expo-router';
import { supabase } from '../lib/supabase';

export default function Index() {
  useEffect(() => {
    supabase.auth.signOut();
  }, []);

  return <Redirect href="/(auth)/welcome" />;
}
