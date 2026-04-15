import { createClient } from '@supabase/supabase-js';
import * as SecureStore from 'expo-secure-store';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!;

// SecureStore has a 2048 byte limit per key — chunk large values
const CHUNK_SIZE = 1900;

const ExpoSecureStoreAdapter = {
  getItem: async (key: string): Promise<string | null> => {
    const chunk0 = await SecureStore.getItemAsync(key);
    if (!chunk0) return null;
    if (!chunk0.startsWith('__CHUNKED__')) return chunk0;
    const count = parseInt(chunk0.replace('__CHUNKED__', ''));
    const chunks = await Promise.all(
      Array.from({ length: count }, (_, i) => SecureStore.getItemAsync(`${key}_${i}`))
    );
    return chunks.join('');
  },
  setItem: async (key: string, value: string): Promise<void> => {
    if (value.length <= CHUNK_SIZE) {
      await SecureStore.setItemAsync(key, value);
      return;
    }
    const chunks = value.match(new RegExp(`.{1,${CHUNK_SIZE}}`, 'g')) ?? [];
    await SecureStore.setItemAsync(key, `__CHUNKED__${chunks.length}`);
    await Promise.all(chunks.map((chunk, i) => SecureStore.setItemAsync(`${key}_${i}`, chunk)));
  },
  removeItem: async (key: string): Promise<void> => {
    const marker = await SecureStore.getItemAsync(key);
    if (marker?.startsWith('__CHUNKED__')) {
      const count = parseInt(marker.replace('__CHUNKED__', ''));
      await Promise.all(
        Array.from({ length: count }, (_, i) => SecureStore.deleteItemAsync(`${key}_${i}`))
      );
    }
    await SecureStore.deleteItemAsync(key);
  },
};

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: ExpoSecureStoreAdapter,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
