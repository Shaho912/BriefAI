import { Tabs } from 'expo-router';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarStyle: { backgroundColor: '#0a0a0a', borderTopColor: '#1a1a1a' },
        tabBarActiveTintColor: '#ffffff',
        tabBarInactiveTintColor: '#555555',
        headerStyle: { backgroundColor: '#0a0a0a' },
        headerTintColor: '#ffffff',
        headerShadowVisible: false,
      }}
    >
      <Tabs.Screen name="today" options={{ title: "Today's Brief", tabBarLabel: 'Today' }} />
      <Tabs.Screen name="history" options={{ title: 'History', tabBarLabel: 'History' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings', tabBarLabel: 'Settings' }} />
    </Tabs>
  );
}
