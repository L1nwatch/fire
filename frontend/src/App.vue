<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activePath = computed(() => {
  if (route.path.startsWith('/holdings')) return '/holdings'
  return '/dashboard'
})
</script>

<template>
  <div class="app-frame">
    <aside class="side-nav">
      <div class="brand-block">
        <p class="brand">Fire</p>
        <p class="brand-sub">Financial independence tracking</p>
      </div>
      <el-menu :default-active="activePath" router class="menu">
        <el-menu-item index="/dashboard">Dashboard</el-menu-item>
        <el-menu-item index="/holdings">Holdings Sheet</el-menu-item>
      </el-menu>
    </aside>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>
