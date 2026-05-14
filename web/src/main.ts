import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { createRouter, createWebHistory } from 'vue-router';
import './style.css';
import HomeView from './views/HomeView.vue';
import ChatView from './views/ChatView.vue';
import MeetingView from './views/MeetingView.vue';
import LiteratureView from './views/LiteratureView.vue';
import PolishView from './views/PolishView.vue';
import PPTView from './views/PPTView.vue';
import TasksView from './views/TasksView.vue';
import SkillsView from './views/SkillsView.vue';

console.log(
  '%c' +
  '  ██╗     ██╗   ██╗██╗   ██╗██╗  ██╗\n' +
  '  ██║     ██║   ██║██║   ██║╚██╗██╔╝\n' +
  '  ██║     ██║   ██║██║   ██║ ╚███╔╝\n' +
  '  ███████╗╚██████╔╝╚██████╔╝ ██╔██╗\n' +
  '  ╚══════╝ ╚═════╝  ╚═════╝  ╚═╝ ╚╝',
  'color: cyan; font-weight: bold;'
);
console.log('%c        L o v e   W o r k i n g', 'color: magenta; font-weight: bold;');
console.log('%c            [ Web ]', 'color: orange; font-weight: bold;');
console.log('%c  ─────────────────────────────────────', 'color: gray;');
console.log('%c  Your AI Office Assistant  |  v1.0.0', 'color: white;');

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/chat', component: ChatView },
    { path: '/meeting', component: MeetingView },
    { path: '/literature', component: LiteratureView },
    { path: '/polish', component: PolishView },
    { path: '/ppt', component: PPTView },
    { path: '/tasks', component: TasksView },
    { path: '/skills', component: SkillsView },
  ],
});

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
