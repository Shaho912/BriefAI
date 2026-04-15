import { useEffect, useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { apiFetch } from '../../lib/api';

type BriefSummary = {
  id: string;
  arxiv_id: string;
  title: string;
  relevance_score: number;
  generated_at: string;
  audio_url: string | null;
};

export default function HistoryScreen() {
  const router = useRouter();
  const [briefs, setBriefs] = useState<BriefSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  function loadBriefs() {
    return apiFetch<{ items: BriefSummary[] }>('/briefs')
      .then(data => setBriefs(data.items));
  }

  useEffect(() => {
    loadBriefs().finally(() => setLoading(false));
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    await loadBriefs().catch(() => {});
    setRefreshing(false);
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#ffffff" /></View>;

  if (!briefs.length) return (
    <View style={styles.center}>
      <Text style={styles.emptyText}>No briefs yet. Check back after your first delivery.</Text>
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={briefs}
      keyExtractor={item => item.id}
      alwaysBounceVertical
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#ffffff" />}
      renderItem={({ item }) => (
        <TouchableOpacity style={styles.card} onPress={() => router.push(`/brief/${item.id}`)}>
          <View style={styles.cardHeader}>
            <Text style={styles.score}>{(item.relevance_score * 100).toFixed(0)}% match</Text>
            <Text style={styles.date}>
              {new Date(item.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </Text>
          </View>
          <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.arxiv}>arXiv:{item.arxiv_id}</Text>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  content: { padding: 16, gap: 12 },
  center: { flex: 1, backgroundColor: '#0a0a0a', justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyText: { color: '#666', fontSize: 16, textAlign: 'center', lineHeight: 26 },
  card: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 18, gap: 8 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  score: { fontSize: 12, color: '#888', fontWeight: '600' },
  date: { fontSize: 12, color: '#555' },
  title: { fontSize: 16, fontWeight: '600', color: '#ffffff', lineHeight: 24 },
  arxiv: { fontSize: 12, color: '#555' },
});
