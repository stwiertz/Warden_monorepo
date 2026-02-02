/**
 * Video player component (FR11-15).
 * Custom UI on top of expo-av with POV/Minimap toggle, timeline, and controls.
 */

import { View, Text, StyleSheet } from 'react-native';

export function VideoPlayer() {
  return (
    <View style={styles.container}>
      <Text>Video Player</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
