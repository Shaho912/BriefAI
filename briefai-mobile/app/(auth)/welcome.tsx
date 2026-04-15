import { View, Text, TouchableOpacity, StyleSheet, Image } from 'react-native';
import { useRouter } from 'expo-router';

export default function WelcomeScreen() {
  const router = useRouter();

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <Image
          source={require('../../assets/briefAI-logo.png')}
          style={styles.logo}
          resizeMode="contain"
        />
        <Text style={styles.title}>Penn Engineering</Text>
        <Text style={styles.subtitle}>
          Your daily research brief,{'\n'}delivered as audio.
        </Text>
      </View>
      <View style={styles.buttons}>
        <TouchableOpacity style={styles.primary} onPress={() => router.push('/(auth)/signup')}>
          <Text style={styles.primaryText}>Get Started</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondary} onPress={() => router.push('/(auth)/login')}>
          <Text style={styles.secondaryText}>Sign In</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a', justifyContent: 'space-between', padding: 32 },
  hero: { flex: 1, justifyContent: 'center' },
  logo: { width: 180, height: 60, marginBottom: 24, tintColor: '#ffffff' },
  title: { fontSize: 32, fontWeight: '700', color: '#ffffff', marginBottom: 12 },
  subtitle: { fontSize: 20, color: '#888888', lineHeight: 30 },
  buttons: { gap: 12 },
  primary: { backgroundColor: '#ffffff', borderRadius: 12, padding: 18, alignItems: 'center' },
  primaryText: { fontSize: 16, fontWeight: '600', color: '#0a0a0a' },
  secondary: { borderRadius: 12, padding: 18, alignItems: 'center' },
  secondaryText: { fontSize: 16, color: '#888888' },
});
