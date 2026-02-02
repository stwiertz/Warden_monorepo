/**
 * Video import screen (FR1-4).
 * Allows users to select and import MP4 video files.
 */

import { View, Text, StyleSheet } from 'react-native';

export function VideoImportScreen() {
  return (
    <View style={styles.container}>
      <Text>Video Import</Text>
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
