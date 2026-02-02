/**
 * Login screen (FR29-30).
 * Firebase authentication UI.
 */

import { View, Text, StyleSheet } from 'react-native';

export function LoginScreen() {
  return (
    <View style={styles.container}>
      <Text>Login</Text>
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
