/**
 * Export screen.
 * Clip range selection, quality options, export progress.
 */

import { View, Text, StyleSheet } from 'react-native';

export function ExportScreen() {
  return (
    <View style={styles.container}>
      <Text>Export Clip</Text>
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
