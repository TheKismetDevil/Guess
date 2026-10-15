<script setup lang="ts">
import InviteCodeTable from '@/components/InviteCodeTable.vue'
</script>

<template>
  <div class="invite-codes-page">
    <header class="ui-page-header">
      <div>
        <span class="ui-page-eyebrow">Admin</span>
        <h1 class="ui-page-title">用户管理</h1>
      </div>
    </header>
    <p class="page-description">
      邀请码是用户注册的唯一凭证。生成时需要绑定 QQ 号，用户注册时需提供匹配的 QQ 号和邀请码。
      已绑定的邀请码可点击「删除」同时移除用户和其投票记录。
    </p>
    <InviteCodeTable />
  </div>
</template>

<style scoped>
.invite-codes-page {
  padding: var(--spacing-5, 20px) var(--spacing-4, 16px);
  max-width: 1280px;
  margin: 0 auto;
}


.page-description {
  font-size: var(--text-body-sm, 14px);
  color: var(--color-ink-secondary, #4A5A4A);
  margin: 0 0 var(--spacing-4, 16px);
  line-height: 1.6;
}
</style>
