<script setup>
import { onMounted, ref } from 'vue';

import { getChatHistory } from './api';
import ChatWindow from './components/ChatWindow.vue';
import Sidebar from './components/Sidebar.vue';

const chatMessages = ref([]);
const sidebarRefreshKey = ref(0);

onMounted(async () => {
  try {
    const { data } = await getChatHistory();
    if (data?.messages) chatMessages.value = data.messages;
  } catch {
    chatMessages.value = [];
  }
});

const handleNewMessage = (message) => {
  chatMessages.value.push(message);
};

const handleChatCleared = () => {
  chatMessages.value = [];
};

const handleWorkspaceUpdated = () => {
  sidebarRefreshKey.value += 1;
};
</script>

<template>
  <Sidebar :refresh-key="sidebarRefreshKey" />
  <ChatWindow
    :messages="chatMessages"
    @message-added="handleNewMessage"
    @message-cleared="handleChatCleared"
    @workspace-updated="handleWorkspaceUpdated"
  />
</template>
