import { defineConfig } from 'vitepress';

export default defineConfig({
  title: 'Hindsight',
  description: 'Review Solidity and track fixes with your AI agent.',
  base: '/docs/',
  srcDir: 'site',
  cleanUrls: false,
  lastUpdated: false,
  head: [
    ['link', { rel: 'icon', href: '/assets/favicon.svg', type: 'image/svg+xml' }],
    ['meta', { name: 'referrer', content: 'strict-origin-when-cross-origin' }]
  ],
  themeConfig: {
    siteTitle: 'Hindsight',
    nav: [
      { text: 'Website', link: '../' },
      { text: 'GitHub', link: 'https://github.com/Shawnchee/hindsight' }
    ],
    sidebar: [
      { text: 'Start here', items: [
        { text: 'Overview', link: '/' },
        { text: 'Get started', link: '/getting-started' },
        { text: 'Review a project', link: '/review' },
        { text: 'Fix and compare', link: '/remediation' }
      ] },
      { text: 'Research & contributions', items: [
        { text: 'Research data', link: '/research' },
        { text: 'Connect via MCP', link: '/mcp' },
        { text: 'Add an incident', link: '/contributing' },
        { text: 'Discovery setup', link: '/discovery' }
      ] },
      { text: 'Reference', items: [
        { text: 'Report format', link: '/report-format' },
        { text: 'Privacy & limits', link: '/privacy' },
        { text: 'Release readiness', link: '/release' }
      ] }
    ],
    search: { provider: 'local' },
    outline: [2, 3],
    footer: { message: 'Early research tooling. A valid report is not a security certificate.' }
  }
});
