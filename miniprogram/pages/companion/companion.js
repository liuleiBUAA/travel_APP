Page({
  data: {
    // 'publish' = 发布路线，'search' = 搜搭子
    tab: 'publish'
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab !== this.data.tab) {
      this.setData({ tab })
    }
  }
})
