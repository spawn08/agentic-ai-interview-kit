import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Agentic AI Interview Kit',
  tagline: 'From foundations to architecture design — your complete guide to agentic AI',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://spawn08.github.io',
  baseUrl: '/agentic-ai-interview-kit/',

  organizationName: 'spawn08',
  projectName: 'agentic-ai-interview-kit',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    mermaid: true,
  },

  themes: [
    '@docusaurus/theme-mermaid',
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        indexBlog: false,
        docsRouteBasePath: '/',
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          showLastUpdateTime: false,
          editUrl:
            'https://github.com/spawn08/agentic-ai-interview-kit/edit/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Agentic AI Interview Kit',
      logo: {
        alt: 'Agentic AI Interview Kit Logo',
        src: 'img/logo.svg',
        srcDark: 'img/logo-dark.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'learningPath',
          position: 'left',
          label: 'Learning Path',
        },
        {
          type: 'docSidebar',
          sidebarId: 'architectureDesign',
          position: 'left',
          label: 'Architecture Design',
        },
        {
          type: 'docSidebar',
          sidebarId: 'projects',
          position: 'left',
          label: 'Real-World Projects',
        },
        {
          type: 'docSidebar',
          sidebarId: 'interviewPrep',
          position: 'left',
          label: 'Interview Prep',
        },
        {
          href: 'https://github.com/spawn08/agentic-ai-interview-kit',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Learn',
          items: [
            {label: 'Foundations', to: '/foundations/llm-fundamentals'},
            {label: 'Core Concepts', to: '/core-concepts/what-are-agents'},
            {label: 'Design Patterns', to: '/design-patterns/react-pattern'},
          ],
        },
        {
          title: 'Build',
          items: [
            {label: 'Frameworks', to: '/frameworks/langchain-overview'},
            {label: 'Architecture Design', to: '/architecture-design/design-principles'},
            {label: 'Real-World Projects', to: '/projects/customer-support-agent'},
          ],
        },
        {
          title: 'Prepare',
          items: [
            {label: 'Interview Questions', to: '/interview-questions/foundational-qa'},
            {label: 'Coding Challenges', to: '/interview-questions/coding-challenges'},
            {
              label: 'GitHub',
              href: 'https://github.com/spawn08/agentic-ai-interview-kit',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Agentic AI Interview Kit. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'yaml'],
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 4,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
