/**
 * Home screen - Session list.
 * Displays imported sessions and provides access to video import.
 */

import { View, Text, StyleSheet } from 'react-native';

export function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Warden</Text>
      <Text style={styles.subtitle}>No sessions yet. Import a video to get started.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
});
