import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { apiFetch } from '../../lib/api';

type Brief = {
  id: string;
  arxiv_id: string;
  title: string;
  authors: string[];
  relevance_score: number;
  brief_text: string;
  audio_url: string | null;
  generated_at: string;
};

const SPEEDS = [0.75, 1.0, 1.25, 1.5];

export default function BriefDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loading, setLoading] = useState(true);
  const [speedIndex, setSpeedIndex] = useState(1);

  const player = useAudioPlayer(brief?.audio_url ? { uri: brief.audio_url } : null);
  const status = useAudioPlayerStatus(player);

  useEffect(() => {
    apiFetch<Brief>(`/briefs/${id}`)
      .then(setBrief)
      .finally(() => setLoading(false));
  }, [id]);

  function togglePlay() {
    if (status.playing) {
      player.pause();
    } else {
      player.play();
    }
  }

  function cycleSpeed() {
    const next = (speedIndex + 1) % SPEEDS.length;
    setSpeedIndex(next);
    player.setPlaybackRate(SPEEDS[next]);
  }

  function formatTime(s: number) {
    return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  }

  const position = status.currentTime ?? 0;
  const duration = status.duration ?? 0;

  if (loading) return <View style={styles.center}><ActivityIndicator color="#ffffff" /></View>;

  if (!brief) return (
    <View style={styles.center}>
      <Text style={styles.emptyText}>Brief not found.</Text>
    </View>
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Paper metadata */}
      <View style={styles.card}>
        <Text style={styles.score}>Relevance {(brief.relevance_score * 100).toFixed(0)}%</Text>
        <Text style={styles.title}>{brief.title}</Text>
        <Text style={styles.authors}>{brief.authors.slice(0, 3).join(', ')}</Text>
        <Text style={styles.arxiv}>arXiv:{brief.arxiv_id}</Text>
        <Text style={styles.date}>
          {new Date(brief.generated_at).toLocaleDateString('en-US', {
            month: 'long', day: 'numeric', year: 'numeric',
          })}
        </Text>
      </View>

      {/* Audio player */}
      {brief.audio_url && (
        <View style={styles.player}>
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: duration ? `${(position / duration) * 100}%` : '0%' }]} />
          </View>
          <View style={styles.timeRow}>
            <Text style={styles.timeText}>{formatTime(position)}</Text>
            <Text style={styles.timeText}>{formatTime(duration)}</Text>
          </View>
          <View style={styles.controls}>
            <TouchableOpacity style={styles.speedButton} onPress={cycleSpeed}>
              <Text style={styles.speedText}>{SPEEDS[speedIndex]}x</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.playButton} onPress={togglePlay}>
              <Text style={styles.playIcon}>{status.playing ? '⏸' : '▶'}</Text>
            </TouchableOpacity>
            <View style={{ width: 56 }} />
          </View>
        </View>
      )}

      {/* Brief text */}
      <View style={styles.briefCard}>
        <Text style={styles.briefText}>{brief.brief_text}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  content: { padding: 20, gap: 16 },
  center: { flex: 1, backgroundColor: '#0a0a0a', justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyText: { color: '#666', fontSize: 16, textAlign: 'center' },
  card: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 20, gap: 8 },
  score: { fontSize: 12, color: '#888', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1 },
  title: { fontSize: 18, fontWeight: '700', color: '#ffffff', lineHeight: 26 },
  authors: { fontSize: 13, color: '#888' },
  arxiv: { fontSize: 12, color: '#555' },
  date: { fontSize: 12, color: '#555' },
  player: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 20, gap: 12 },
  progressBar: { height: 4, backgroundColor: '#333', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#ffffff', borderRadius: 2 },
  timeRow: { flexDirection: 'row', justifyContent: 'space-between' },
  timeText: { fontSize: 12, color: '#666' },
  controls: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  speedButton: { backgroundColor: '#333', borderRadius: 8, padding: 10, width: 56, alignItems: 'center' },
  speedText: { color: '#ffffff', fontSize: 13, fontWeight: '600' },
  playButton: { backgroundColor: '#ffffff', borderRadius: 32, width: 64, height: 64, alignItems: 'center', justifyContent: 'center' },
  playIcon: { fontSize: 24, color: '#0a0a0a' },
  briefCard: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 20 },
  briefText: { color: '#cccccc', fontSize: 15, lineHeight: 26 },
});
