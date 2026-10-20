import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import { LiteTree } from 'vitepress-plugin-tree'
import Wordmark from './Wordmark.vue'
import './labnotes.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Tree', LiteTree)
  },
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-title-after': () => h(Wordmark),
      'home-hero-info-before': () => h('h1', { class: 'hero-wordmark' }, h(Wordmark)),
    }),
}
