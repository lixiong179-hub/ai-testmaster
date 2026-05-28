<template>
  <router-view />
</template>

<script setup lang="ts">
// Root shell.
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
}

body {
  font-family:
    'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial,
    sans-serif;
  font-size: 14px;
  color: #333;
  background-color: #f5f7fa;
  overflow: hidden;
}

a {
  color: inherit;
  text-decoration: none;
}
</style>
