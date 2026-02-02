/**
 * Root layout - React Navigation container.
 * Orchestrates navigation between main screens.
 */

import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { HomeScreen } from './index';
import { SessionScreen } from './session/[id]';
import { ExportScreen } from './session/export';

export type RootStackParamList = {
  Home: undefined;
  Session: { id: string };
  Export: { sessionId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootLayout() {
  return (
    <NavigationContainer>
      <StatusBar style="auto" />
      <Stack.Navigator
        initialRouteName="Home"
        screenOptions={{
          headerShown: true,
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: 'Warden' }}
        />
        <Stack.Screen
          name="Session"
          component={SessionScreen}
          options={{ title: 'Session Review' }}
        />
        <Stack.Screen
          name="Export"
          component={ExportScreen}
          options={{ title: 'Export Clip' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
