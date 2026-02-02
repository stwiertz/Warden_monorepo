/**
 * Session review screen.
 * Main review interface: video player, episode navigation, audio commentary.
 */

import { View, Text, StyleSheet } from 'react-native';

export function SessionScreen() {
  return (
    <View style={styles.container}>
      <Text>Session Review</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
