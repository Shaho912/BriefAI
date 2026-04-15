import { useState, useRef, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { apiFetch, apiStream } from '../../lib/api';

type Message = { role: 'user' | 'assistant'; content: string };

const SENTINEL = 'REQUIREMENTS_COMPLETE';

export default function OnboardingScreen() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const listRef = useRef<FlatList>(null);

  // Create session and get opening message on mount
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const { session_id } = await apiFetch<{ session_id: string }>('/onboarding/session', {
          method: 'POST',
          body: JSON.stringify({}),
        });
        setSessionId(session_id);

        // Get opening message
        const opening = await apiFetch<{ message: string }>(
          `/onboarding/session/${session_id}/opening`,
          { method: 'POST' },
        );
        const reply = opening.message ?? '';
        setMessages([{ role: 'assistant', content: reply }]);
        if (reply.includes(SENTINEL)) setIsComplete(true);
      } catch (e) {
        console.error('Onboarding init failed:', e);
        setMessages([{ role: 'assistant', content: `Error: ${e instanceof Error ? e.message : String(e)}` }]);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  async function sendMessage() {
    if (!input.trim() || !sessionId || loading) return;
    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    let reply = '';
    try {
      await apiStream(
        `/onboarding/session/${sessionId}/message`,
        {
          method: 'POST',
          body: JSON.stringify({ content: userMessage }),
        },
        (chunk) => {
          reply += chunk;
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === 'assistant') {
              updated[updated.length - 1] = { role: 'assistant', content: reply };
            } else {
              updated.push({ role: 'assistant', content: reply });
            }
            return updated;
          });
        },
      );
      if (reply.includes(SENTINEL)) setIsComplete(true);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  }

  async function finishOnboarding() {
    if (!sessionId) return;
    setFinishing(true);
    try {
      await apiFetch(`/onboarding/session/${sessionId}/complete`, { method: 'POST' });
      router.replace('/(tabs)/today');
    } catch {
      setFinishing(false);
    }
  }

  // Clean SENTINEL from displayed text
  function cleanContent(content: string) {
    return content.replace(SENTINEL, '').trim();
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Set up your profile</Text>
        <Text style={styles.headerSub}>Tell us what you research</Text>
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.messages}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.aiBubble]}>
            <Text style={[styles.bubbleText, item.role === 'user' ? styles.userText : styles.aiText]}>
              {cleanContent(item.content)}
            </Text>
          </View>
        )}
      />

      {isComplete ? (
        <TouchableOpacity style={styles.finishButton} onPress={finishOnboarding} disabled={finishing}>
          {finishing
            ? <ActivityIndicator color="#0a0a0a" />
            : <Text style={styles.finishText}>Looks good — finish setup</Text>}
        </TouchableOpacity>
      ) : (
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Type a message..."
            placeholderTextColor="#555"
            value={input}
            onChangeText={setInput}
            onSubmitEditing={sendMessage}
            returnKeyType="send"
            editable={!loading}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} onPress={sendMessage} disabled={loading || !input.trim()}>
            {loading ? <ActivityIndicator color="#ffffff" size="small" /> : <Text style={styles.sendText}>→</Text>}
          </TouchableOpacity>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  header: { padding: 24, paddingTop: 60, borderBottomWidth: 1, borderBottomColor: '#1a1a1a' },
  headerTitle: { fontSize: 22, fontWeight: '700', color: '#ffffff' },
  headerSub: { fontSize: 14, color: '#666', marginTop: 4 },
  messages: { padding: 16, gap: 12 },
  bubble: { maxWidth: '80%', borderRadius: 16, padding: 14 },
  userBubble: { backgroundColor: '#ffffff', alignSelf: 'flex-end' },
  aiBubble: { backgroundColor: '#1a1a1a', alignSelf: 'flex-start' },
  bubbleText: { fontSize: 15, lineHeight: 22 },
  userText: { color: '#0a0a0a' },
  aiText: { color: '#ffffff' },
  inputRow: { flexDirection: 'row', padding: 16, gap: 8, borderTopWidth: 1, borderTopColor: '#1a1a1a' },
  input: {
    flex: 1, backgroundColor: '#1a1a1a', borderRadius: 12,
    padding: 14, color: '#ffffff', fontSize: 15, maxHeight: 100,
  },
  sendButton: {
    backgroundColor: '#ffffff', borderRadius: 12,
    width: 48, alignItems: 'center', justifyContent: 'center',
  },
  sendText: { fontSize: 20, color: '#0a0a0a' },
  finishButton: {
    margin: 16, backgroundColor: '#ffffff', borderRadius: 12,
    padding: 18, alignItems: 'center',
  },
  finishText: { fontSize: 16, fontWeight: '600', color: '#0a0a0a' },
});
