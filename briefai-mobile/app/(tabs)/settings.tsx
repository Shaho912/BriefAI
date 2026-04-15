import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, ActivityIndicator, Alert, RefreshControl,
} from 'react-native';
import { supabase } from '../../lib/supabase';
import { apiFetch } from '../../lib/api';

type Settings = {
  focus_text: string;
  arxiv_categories: string[];
  relevance_threshold: number;
  elevenlabs_voice_id: string;
  delivery_hour_utc: number;
};

type SubscriptionStatus = {
  tier: 'free' | 'paid';
  status: string;
  expires_at: string | null;
};

export default function SettingsScreen() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  function loadSettings() {
    return Promise.all([
      apiFetch<Settings>('/settings'),
      apiFetch<SubscriptionStatus>('/subscriptions/status'),
    ]).then(([s, sub]) => {
      setSettings(s);
      setSubscription(sub);
    });
  }

  useEffect(() => {
    loadSettings().finally(() => setLoading(false));
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    await loadSettings().catch(() => {});
    setRefreshing(false);
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#ffffff" /></View>;

  const isPaid = subscription?.tier === 'paid';

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      alwaysBounceVertical
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#ffffff" />}
    >

      {/* Subscription status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Plan</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.label}>{isPaid ? 'Pro' : 'Free'}</Text>
            <Text style={styles.badge}>{isPaid ? 'Daily briefs' : '3/week'}</Text>
          </View>
          {!isPaid && (
            <TouchableOpacity
              style={styles.upgradeButton}
              onPress={() => Alert.alert('Upgrade', 'In-app purchases coming soon.')}
            >
              <Text style={styles.upgradeText}>Upgrade to Pro</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Research focus */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Research Focus</Text>
        <View style={styles.card}>
          <Text style={styles.focusText}>{settings?.focus_text}</Text>
        </View>
      </View>

      {/* arXiv categories */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>arXiv Categories</Text>
          {!isPaid && <Text style={styles.lockBadge}>Pro only</Text>}
        </View>
        <View style={styles.card}>
          <View style={styles.chips}>
            {settings?.arxiv_categories.map(cat => (
              <View key={cat} style={styles.chip}>
                <Text style={styles.chipText}>{cat}</Text>
              </View>
            ))}
          </View>
          {!isPaid && (
            <Text style={styles.lockedNote}>Upgrade to customize your arXiv categories.</Text>
          )}
        </View>
      </View>

      {/* Delivery time */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Delivery Time</Text>
          {!isPaid && <Text style={styles.lockBadge}>Pro only</Text>}
        </View>
        <View style={styles.card}>
          <Text style={styles.label}>
            {settings?.delivery_hour_utc !== undefined
              ? `${settings.delivery_hour_utc}:00 UTC`
              : '—'}
          </Text>
          {!isPaid && (
            <Text style={styles.lockedNote}>Upgrade to set a custom delivery time.</Text>
          )}
        </View>
      </View>

      {/* Sign out */}
      <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  content: { padding: 20, gap: 24 },
  center: { flex: 1, backgroundColor: '#0a0a0a', justifyContent: 'center', alignItems: 'center' },
  section: { gap: 10 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: { fontSize: 13, fontWeight: '600', color: '#888', textTransform: 'uppercase', letterSpacing: 1 },
  lockBadge: { fontSize: 11, color: '#555', backgroundColor: '#1a1a1a', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  card: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 18, gap: 12 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { fontSize: 16, color: '#ffffff', fontWeight: '500' },
  badge: { fontSize: 13, color: '#888' },
  upgradeButton: { backgroundColor: '#ffffff', borderRadius: 10, padding: 14, alignItems: 'center' },
  upgradeText: { fontSize: 15, fontWeight: '600', color: '#0a0a0a' },
  focusText: { fontSize: 15, color: '#cccccc', lineHeight: 24 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { backgroundColor: '#333', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  chipText: { fontSize: 13, color: '#ffffff' },
  lockedNote: { fontSize: 13, color: '#555' },
  signOutButton: { borderRadius: 12, padding: 18, alignItems: 'center', borderWidth: 1, borderColor: '#333' },
  signOutText: { fontSize: 16, color: '#888' },
});
