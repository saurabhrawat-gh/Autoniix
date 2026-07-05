import React from 'react';
import type { Preview } from '@storybook/react';
import { NextIntlClientProvider } from 'next-intl';
import '../src/app/globals.css';
import messages from '../messages/en.json';

const preview: Preview = {
  globalTypes: {
    theme: {
      description: 'Global theme',
      defaultValue: 'light',
      toolbar: {
        title: 'Theme',
        icon: 'paintbrush',
        items: [
          { value: 'light', title: 'Light', icon: 'sun' },
          { value: 'dark', title: 'Dark', icon: 'moon' },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story, context) => {
      const theme = context.globals.theme as string;
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', theme === 'dark');
      }
      return React.createElement(
        NextIntlClientProvider,
        { locale: 'en', messages, children: React.createElement(Story) }
      );
    },
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: { disable: true },
    a11y: {
      element: '#storybook-root',
      config: {},
      options: {
        runOnly: {
          type: 'tag',
          values: ['wcag2a', 'wcag2aa'],
        },
      },
    },
  },
};

export default preview;
