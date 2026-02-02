import { Pressable, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export function Button({ title, onPress, variant = 'primary', disabled = false }: ButtonProps) {
  return (
    <Pressable
      style={[styles.button, variant === 'secondary' && styles.secondary, disabled && styles.disabled]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text style={[styles.text, variant === 'secondary' && styles.secondaryText]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  } as ViewStyle,
  secondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#007AFF',
  } as ViewStyle,
  disabled: {
    opacity: 0.5,
  } as ViewStyle,
  text: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  } as TextStyle,
  secondaryText: {
    color: '#007AFF',
  } as TextStyle,
});
