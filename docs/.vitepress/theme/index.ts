import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import Wordmark from './Wordmark.vue'
import './labnotes.css'

export default {
  extends: DefaultTheme,
  Layout: () => h(DefaultTheme.Layout, null, { 'nav-bar-title-after': () => h(Wordmark) }),
}
