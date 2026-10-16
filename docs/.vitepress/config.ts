import { defineConfig } from 'vitepress'

// Per-project value: a clone renames this along with the identical
// `repository` URLs in packages/{node/package.json,python/pyproject.toml,rust/Cargo.toml}
// (a find-and-replace of the URL covers all of them) and `base` below.
const repository = 'https://github.com/thekevinscott/template-lib'

export default defineConfig({
  title: '',
  description: '',
  base: '/template-lib/',
  cleanUrls: true,
  // AGENTS.md is an agent-facing contract, not site content — keep it out of
  // the build. The changelog/migration fragment folders are the raw record
  // (one file per PR, see docs/internals/repo.md); they never publish either.
  // internals/ is contributor/agent-facing material, also excluded.
  srcExclude: ['**/AGENTS.md', 'changelog.d/**', 'migrations.d/**', 'internals/**'],
  themeConfig: {
    // Top-level nav is the four Diataxis quadrants, mirroring the
    // testing-conventions docs site. See docs/AGENTS.md.
    nav: [
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'How-to Guides', link: '/guide/' },
      { text: 'Reference', link: '/reference/' },
      { text: 'Explanation', link: '/explanation/' },
    ],
    sidebar: {
      '/': [
        {
          text: 'Tutorial',
          items: [
            { text: 'Getting Started', link: '/getting-started' },
          ],
        },
        {
          text: 'How-to Guides',
          items: [
            { text: 'Overview', link: '/guide/' },
            { text: 'Testing conventions', link: '/guide/testing-conventions' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'API', link: '/reference/' },
            { text: 'Migrations', link: '/migrations' },
          ],
        },
        {
          text: 'Explanation',
          items: [
            { text: 'Overview', link: '/explanation/' },
          ],
        },
      ],
    },
    socialLinks: [{ icon: 'github', link: repository }],
    search: { provider: 'local' },
    outline: [2, 3],
  },
})
