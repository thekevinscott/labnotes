import { defineConfig } from 'vitepress'

const repository = 'https://github.com/thekevinscott/labnotes'

export default defineConfig({
  vue: { template: { compilerOptions: { whitespace: 'preserve' } } },
  title: 'labnotes',
  description: '',
  base: '/labnotes/',
  cleanUrls: true,
  // AGENTS.md is an agent-facing contract, not site content — keep it out of
  // the build. The changelog/migration fragment folders are the raw record
  // (one file per PR, see docs/internals/repo.md); they never publish either.
  // internals/ is contributor/agent-facing material, also excluded.
  // migrations.md is a pointer stub at the conventional path.
  srcExclude: ['**/AGENTS.md', 'changelog.d/**', 'migrations.d/**', 'internals/**', 'migrations.md'],
  themeConfig: {
    siteTitle: false,
    sidebar: [
      {
        items: [
          { text: 'Philosophy', link: '/philosophy' },
          { text: 'Getting Started', link: '/getting-started' },
          {
            text: 'CLI',
            items: [
              { text: 'Working with Experiments', link: '/cli/experiments' },
              { text: 'Adhoc', link: '/cli/adhoc' },
              { text: 'Grid', link: '/cli/grid' },
            ],
          },
          { text: 'Frontend', link: '/frontend' },
          { text: 'Skill', link: '/skill' },
        ],
      },
      {
        text: 'API',
        items: [{ text: 'Config', link: '/api/config' }],
      },
    ],
    socialLinks: [{ icon: 'github', link: repository }],
    search: { provider: 'local' },
    outline: [2, 3],
  },
})
