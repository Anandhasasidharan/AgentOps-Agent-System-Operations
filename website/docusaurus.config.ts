import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'AgentOps',
  tagline: 'AI Agent Safety & Observability Platform',
  favicon: 'img/favicon.ico',

  url: 'https://anandhasasidharan.github.io',
  baseUrl: '/AgentOps-Agent-System-Operations/',

  organizationName: 'Anandhasasidharan',
  projectName: 'AgentOps-Agent-System-Operations',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/website/',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'AgentOps',
      logo: {
        alt: 'AgentOps Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {label: 'Overview', to: '/'},
            {label: 'Architecture', to: '/architecture'},
            {label: 'Circuit Breaker', to: '/circuit-breaker'},
            {label: 'Chaos Toolkit', to: '/chaos-toolkit'},
            {label: 'SLO Platform', to: '/slo-platform'},
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations',
            },
            {
              label: 'Docker Hub',
              href: 'https://hub.docker.com/u/asd492',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} AgentOps. MIT License.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
