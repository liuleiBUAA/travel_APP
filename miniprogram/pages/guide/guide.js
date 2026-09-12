const api = require('../../utils/api')
const app = getApp()

// 城市分组配置（纯展示层）：仅目的地数量多的国家分组，其余国家平铺。
// key = 国家名（与后端 destinations 目录一致）；顺序即渲染顺序。
const CITY_GROUPS = {
  '美国东部中部': [
    { icon: '🏙️', title: '东北都会', cities: ['纽约', '波士顿', '华盛顿', '费城', '尼亚加拉瀑布'] },
    { icon: '⛰️', title: '阿巴拉契亚山区', cities: ['阿卡迪亚国家公园', '大雾山国家公园', '仙纳度国家公园', '美东“蓝岭公路与双园”大环线'] },
    { icon: '🌴', title: '佛州 & 南方', cities: ['奥兰多', '迈阿密', '坦帕', '亚特兰大', '大沼泽地国家公园', '新奥尔良', '休斯顿'] },
    { icon: '🌾', title: '中西部 & 落基山', cities: ['芝加哥', '密歇根湖“巨型沙丘与五彩悬崖”大环线', '丹佛', '洛基山国家公园'] },
    { icon: '🔄', title: '跨城大环线', cities: ['🔄 波士顿+阿卡迪亚环线'] },
  ],
  '美国西部': [
    { icon: '🌉', title: '加州海岸都会', cities: ['旧金山', '洛杉矶', '圣地亚哥', '1号公路', '红杉国家公园'] },
    { icon: '🎰', title: '内华达 & 峡谷沙漠', cities: ['拉斯维加斯', '死亡谷国家公园', '🔄 羚羊谷+大峡谷2日环线'] },
    { icon: '🌲', title: '山地国家公园', cities: ['优胜美地国家公园', '冰川国家公园', '🔄 黄石大提顿环线'] },
    { icon: '🌧️', title: '西北太平洋', cities: ['西雅图', '波特兰', '火山口湖国家公园', '华盛顿州“海山冰川”大环线'] },
    { icon: '🔄', title: '跨州大环线', cities: ['🔄 精华版美西环线'] },
  ],
  // ---- 国内 19 个地区（只勾城市打包发帖，不生成路线）----
  '新疆': [
    { icon: '🏙', title: '乌鲁木齐及周边', cities: ['乌鲁木齐', '天山天池', '天山大峡谷', '江布拉克·奇台'] },
    { icon: '🏔', title: '北疆·喀纳斯阿勒泰', cities: ['喀纳斯·禾木', '白哈巴', '五彩滩·布尔津', '可可托海', '白沙湖·哈巴河', '阿勒泰'] },
    { icon: '🌾', title: '伊犁·赛里木湖', cities: ['伊宁·伊犁河谷', '伊犁·那拉提', '喀拉峻', '唐布拉', '昭苏', '果子沟', '赛里木湖', '独库公路'] },
    { icon: '🐎', title: '巴州·巴音布鲁克', cities: ['巴音布鲁克', '博斯腾湖', '库尔勒', '罗布人村寨'] },
    { icon: '🕌', title: '南疆·喀什帕米尔', cities: ['库车大峡谷', '温宿大峡谷·托木尔', '阿克苏', '喀什', '帕米尔·塔县', '和田', '泽普金湖杨'] },
    { icon: '🏜', title: '吐鲁番·克拉玛依', cities: ['吐鲁番', '魔鬼城·乌尔禾', '克拉玛依', '塔克拉玛干沙漠公路'] },
  ],
  '西藏': [
    { icon: '🛕', title: '拉萨及周边', cities: ['拉萨', '纳木错', '羊卓雍措', '山南'] },
    { icon: '🌲', title: '林芝·藏东南', cities: ['林芝', '雅鲁藏布大峡谷', '巴松措', '鲁朗林海', '南迦巴瓦·索松村', '然乌湖', '米堆冰川', '墨脱', '昌都'] },
    { icon: '🏔', title: '日喀则·珠峰', cities: ['日喀则', '珠峰大本营', '吉隆沟'] },
    { icon: '🕉', title: '阿里·那曲', cities: ['阿里·冈仁波齐', '玛旁雍错', '扎达土林·古格', '色林错', '那曲'] },
  ],
  '大西北': [
    { icon: '🏞', title: '青海环线', cities: ['西宁', '塔尔寺', '门源油菜花', '祁连·卓尔山', '阿咪东索', '青海湖', '茶卡盐湖'] },
    { icon: '🧂', title: '柴达木·戈壁', cities: ['翡翠湖·大柴旦', '察尔汗盐湖', '格尔木', '冷湖·火星营地'] },
    { icon: '🐪', title: '河西走廊', cities: ['敦煌', '敦煌雅丹·玉门关', '嘉峪关', '张掖七彩丹霞', '马蹄寺', '山丹军马场', '武威', '兰州', '黄河石林·白银'] },
    { icon: '🛕', title: '甘南·陇东南', cities: ['天水·麦积山', '崆峒山·平凉', '甘南·扎尕那', '郎木寺', '夏河·拉卜楞寺', '官鹅沟'] },
    { icon: '🏜', title: '宁夏', cities: ['银川', '贺兰山·镇北堡', '沙湖', '水洞沟', '沙坡头·中卫', '青铜峡黄河大峡谷', '六盘山'] },
    { icon: '🌵', title: '内蒙额济纳', cities: ['额济纳', '阿拉善·巴丹吉林沙漠'] },
  ],
  '川渝': [
    { icon: '🐼', title: '成都平原·川东', cities: ['成都', '都江堰·青城山', '乐山大佛', '峨眉山', '阆中古城', '剑门关·广元', '宜宾蜀南竹海', '自贡'] },
    { icon: '🏔', title: '川西·甘孜阿坝', cities: ['九寨沟', '黄龙', '若尔盖草原', '四姑娘山', '丹巴甲居藏寨', '色达', '稻城亚丁', '新都桥', '海螺沟', '康定·塔公草原', '毕棚沟·理县'] },
    { icon: '🌉', title: '重庆', cities: ['重庆', '武隆天生三桥', '大足石刻', '金佛山', '龚滩古镇·酉阳', '长江三峡·巫山'] },
  ],
  '云南': [
    { icon: '🌺', title: '昆明·滇中', cities: ['昆明', '石林', '抚仙湖', '东川红土地', '罗平油菜花'] },
    { icon: '🏯', title: '大理·丽江', cities: ['大理', '双廊', '沙溪古镇', '丽江', '束河古镇', '玉龙雪山', '泸沽湖'] },
    { icon: '🏔', title: '迪庆·香格里拉', cities: ['香格里拉', '普达措', '虎跳峡', '梅里雪山·雨崩', '怒江·丙中洛'] },
    { icon: '♨️', title: '滇西·腾冲', cities: ['腾冲', '和顺古镇', '瑞丽'] },
    { icon: '🌴', title: '滇南·西双版纳', cities: ['西双版纳', '普洱'] },
    { icon: '🌾', title: '滇东南·红河', cities: ['元阳梯田', '建水古城', '普者黑'] },
  ],
  '贵州': [
    { icon: '🏙', title: '贵阳及周边', cities: ['贵阳', '青岩古镇', '织金洞'] },
    { icon: '💧', title: '黔南·安顺', cities: ['黄果树瀑布', '荔波小七孔', '安顺屯堡'] },
    { icon: '🪘', title: '黔东南', cities: ['西江千户苗寨', '镇远古城', '肇兴侗寨', '加榜梯田', '梵净山'] },
    { icon: '🍶', title: '黔北·遵义赤水', cities: ['遵义', '赤水丹霞', '四洞沟'] },
    { icon: '⛰', title: '黔西南', cities: ['万峰林·兴义', '马岭河峡谷'] },
  ],
  '广西': [
    { icon: '🎏', title: '桂林山水', cities: ['桂林', '阳朔', '遇龙河'] },
    { icon: '🌾', title: '桂北民俗', cities: ['龙脊梯田·龙胜', '三江程阳侗寨', '黄姚古镇·贺州', '兴安灵渠'] },
    { icon: '🏖', title: '北部湾海滨', cities: ['北海银滩', '涠洲岛', '钦州三娘湾'] },
    { icon: '🌊', title: '桂西南边关', cities: ['南宁', '德天跨国瀑布', '通灵大峡谷', '巴马'] },
  ],
  '海南': [
    { icon: '🏝', title: '三亚湾区', cities: ['三亚', '亚龙湾', '海棠湾', '蜈支洲岛'] },
    { icon: '🌊', title: '东线海岸', cities: ['分界洲岛·陵水', '日月湾·万宁', '博鳌·琼海', '文昌'] },
    { icon: '🌴', title: '海口·中部', cities: ['海口', '五指山', '儋州'] },
  ],
  '湖南·湖北': [
    { icon: '⛰', title: '张家界·湘西', cities: ['张家界', '天门山', '袁家界', '凤凰古城', '芙蓉镇', '矮寨大桥'] },
    { icon: '🏙', title: '长沙·湘中南', cities: ['长沙', '南岳衡山', '崀山', '岳阳楼·洞庭湖', '韶山'] },
    { icon: '🌉', title: '武汉·鄂东', cities: ['武汉', '黄鹤楼', '荆州古城', '襄阳古城'] },
    { icon: '🏞', title: '鄂西·恩施神农架', cities: ['恩施大峡谷', '清江画廊', '神农架', '三峡大坝·宜昌'] },
    { icon: '🛕', title: '武当山', cities: ['武当山'] },
  ],
  '江浙沪': [
    { icon: '🏙', title: '上海', cities: ['上海', '朱家角', '佘山'] },
    { icon: '🌉', title: '杭州·嘉湖', cities: ['杭州西湖', '千岛湖', '莫干山', '乌镇', '西塘', '南浔', '绍兴'] },
    { icon: '🏝', title: '浙东·舟山海岛', cities: ['宁波', '普陀山', '东极岛', '嵊泗列岛', '象山石浦'] },
    { icon: '⛰', title: '浙南山水', cities: ['雁荡山', '楠溪江', '缙云仙都', '温州'] },
    { icon: '🏯', title: '南京·苏锡常', cities: ['南京', '苏州', '周庄', '同里', '无锡鼋头渚', '常州'] },
    { icon: '🌸', title: '苏中·扬州', cities: ['扬州瘦西湖', '镇江', '南通'] },
  ],
  '福建': [
    { icon: '🏝', title: '厦漳泉', cities: ['厦门', '鼓浪屿', '泉州', '南靖云水谣土楼', '永定土楼', '东山岛'] },
    { icon: '🍃', title: '闽北·武夷', cities: ['武夷山', '泰宁大金湖', '三明格氏栲'] },
    { icon: '📷', title: '闽东·福州宁德', cities: ['福州三坊七巷', '平潭岛', '霞浦滩涂', '太姥山', '湄洲岛·莆田'] },
  ],
  '安徽·江西': [
    { icon: '🏔', title: '皖南·黄山徽州', cities: ['黄山', '宏村', '西递', '徽州古城', '塔川', '九华山'] },
    { icon: '⛰', title: '皖中·皖西', cities: ['天柱山', '合肥', '天堂寨'] },
    { icon: '🌼', title: '赣东北·婺源三清山', cities: ['婺源', '景德镇', '三清山', '龙虎山', '鄱阳湖'] },
    { icon: '🏞', title: '赣中·赣西', cities: ['庐山', '南昌滕王阁', '井冈山', '武功山', '明月山'] },
  ],
  '陕西·山西': [
    { icon: '🏯', title: '西安·关中', cities: ['西安', '兵马俑', '华山', '法门寺·宝鸡', '乾陵'] },
    { icon: '🟤', title: '陕北', cities: ['延安', '壶口瀑布', '靖边波浪谷', '榆林'] },
    { icon: '🌿', title: '陕南', cities: ['汉中', '太白山', '华阳古镇'] },
    { icon: '🛕', title: '晋北·大同五台', cities: ['云冈石窟·大同', '悬空寺', '恒山', '五台山', '雁门关'] },
    { icon: '🏮', title: '晋中·平遥', cities: ['平遥古城', '王家大院', '乔家大院', '太原', '绵山'] },
    { icon: '🧗', title: '晋南·晋西', cities: ['碛口古镇', '鹳雀楼·永济', '洪洞大槐树'] },
  ],
  '河南': [
    { icon: '🛕', title: '洛阳·郑州', cities: ['洛阳龙门石窟', '老君山', '嵩山少林寺', '郑州', '开封'] },
    { icon: '🏞', title: '太行山水', cities: ['云台山', '郭亮村·万仙山', '龙潭大峡谷', '尧山'] },
    { icon: '🏺', title: '豫北·豫南', cities: ['安阳殷墟', '鸡公山·信阳'] },
  ],
  '山东': [
    { icon: '🏖', title: '胶东海滨', cities: ['青岛', '崂山', '威海·刘公岛', '蓬莱·烟台', '荣成天鹅湖', '日照'] },
    { icon: '⛰', title: '鲁中·济南泰山', cities: ['泰山', '济南', '淄博', '沂蒙山'] },
    { icon: '🏯', title: '鲁南·曲阜', cities: ['曲阜三孔', '台儿庄古城', '微山湖'] },
  ],
  '东北': [
    { icon: '❄️', title: '哈尔滨·雪乡', cities: ['哈尔滨', '中央大街', '雪乡', '亚布力', '镜泊湖'] },
    { icon: '🧭', title: '黑龙江北疆', cities: ['漠河·北极村', '伊春', '五大连池', '抚远·黑龙江源'] },
    { icon: '🏔', title: '长白山·吉林', cities: ['长白山', '雾凇岛', '长春', '查干湖', '集安'] },
    { icon: '🌊', title: '辽宁滨海', cities: ['大连', '金石滩', '沈阳', '丹东·鸭绿江', '红海滩·盘锦', '本溪水洞', '兴城'] },
  ],
  '内蒙古': [
    { icon: '🌲', title: '呼伦贝尔·大兴安岭', cities: ['呼伦贝尔', '海拉尔', '额尔古纳', '满洲里', '根河·敖鲁古雅', '阿尔山'] },
    { icon: '🐎', title: '锡林郭勒·乌兰布统', cities: ['乌兰布统', '锡林郭勒草原', '希拉穆仁草原', '克什克腾·阿斯哈图'] },
    { icon: '🏜', title: '河套·库布齐', cities: ['呼和浩特', '库布齐响沙湾', '鄂尔多斯', '包头·五当召'] },
  ],
  '广东·港澳': [
    { icon: '🏙', title: '广深珠', cities: ['广州', '深圳', '珠海'] },
    { icon: '🍜', title: '潮汕', cities: ['潮州', '汕头南澳岛', '揭阳'] },
    { icon: '🏖', title: '粤西海岸', cities: ['海陵岛·阳江', '双月湾·惠州', '湛江', '茂名浪漫海岸'] },
    { icon: '⛰', title: '粤北山水', cities: ['丹霞山·韶关', '开平碉楼', '南昆山'] },
    { icon: '🎡', title: '港澳', cities: ['香港', '澳门'] },
  ],
  '京津冀': [
    { icon: '🏯', title: '北京', cities: ['北京', '慕田峪长城', '古北水镇', '箭扣长城'] },
    { icon: '🌉', title: '天津·环京', cities: ['天津', '承德避暑山庄', '正定', '白洋淀'] },
    { icon: '🐎', title: '冀北草原·坝上', cities: ['丰宁坝上草原', '崇礼·张家口', '草原天路'] },
    { icon: '🏖', title: '冀东海滨', cities: ['北戴河·秦皇岛', '山海关', '乐亭浅水湾'] },
  ],
}

// 国内地区集合：国内不接路线引擎（无国内交通数据），只勾城市 → 打包发帖
const CN_REGION = 'China'

// 把扁平城市列表按 CITY_GROUPS 切成分组；未命中的城市兜底进「更多」组，保证一城不落。
function buildCityGroups(country, cities) {
  const defs = CITY_GROUPS[country]
  if (!defs) return []
  const byName = {}
  cities.forEach(c => { byName[c.name] = c })
  const used = {}
  const groups = []
  defs.forEach(def => {
    const list = []
    def.cities.forEach(name => {
      if (byName[name]) { list.push(byName[name]); used[name] = true }
    })
    if (list.length) groups.push({ icon: def.icon, title: def.title, cities: list })
  })
  const leftover = cities.filter(c => !used[c.name])
  if (leftover.length) groups.push({ icon: '📍', title: '更多', cities: leftover })
  return groups
}

Page({
  data: {
    guideMode: 'recommend',   // 'recommend' 帮我推荐 | 'pick' 知道去哪
    // 攻略搜索
    guideSearchInput: '',
    guideSearchResults: [],
    guideSearched: false,
    selectedCities: [],
    // 「知道去哪」模式：自己选城
    pickSearchInput: '',
    pickSuggestions: [],
    pickCountries: [],
    pickCurrentCountry: '',
    pickCities: [],
    pickGroups: [],   // 城市分组（有则按分区渲染，无则扁平）
    isCN: false,      // 当前是否国内区域：城市卡只显示名字、不生成路线
    showRouteOptions: false,  // 路线高级选项折叠
    // 推荐
    monthOptions: [
      { value: 1, label: '1月 - 冬季' }, { value: 2, label: '2月 - 冬季' },
      { value: 3, label: '3月 - 春季' }, { value: 4, label: '4月 - 春季' },
      { value: 5, label: '5月 - 春季' }, { value: 6, label: '6月 - 夏季' },
      { value: 7, label: '7月 - 夏季' }, { value: 8, label: '8月 - 夏季' },
      { value: 9, label: '9月 - 秋季' }, { value: 10, label: '10月 - 秋季' },
      { value: 11, label: '11月 - 秋季' }, { value: 12, label: '12月 - 冬季' }
    ],
    monthIndex: 4,
    recommendDays: '',
    regionOptions: [
      { value: 'Europe', label: '欧洲', cn: '欧洲' },
      { value: 'Asia', label: '亚洲', cn: '亚洲' },
      { value: 'North_America', label: '北美', cn: '北美' },
      { value: 'Oceania', label: '大洋洲', cn: '大洋洲' },
      { value: CN_REGION, label: '国内', cn: '国内' }
    ],
    // 「帮我推荐」不含国内：国内无交通数据，推荐会调路线引擎
    recommendRegionOptions: [
      { value: 'Europe', label: '欧洲', cn: '欧洲' },
      { value: 'Asia', label: '亚洲', cn: '亚洲' },
      { value: 'North_America', label: '北美', cn: '北美' },
      { value: 'Oceania', label: '大洋洲', cn: '大洋洲' }
    ],
    recommendRegion: 'Europe',
    recommendCountries: [],
    recommendSelectedCountries: [],
    tagOptions: [
      { value: '自然风光', label: '🏞️ 自然风光' },
      { value: '人文历史', label: '🏛️ 人文历史' },
      { value: '海岛海滨', label: '🏖️ 海岛海滨' },
      { value: '现代都市', label: '🏙️ 现代都市' },
      { value: '户外探险', label: '⛰️ 户外探险' },
      { value: '小镇村落', label: '🏘️ 小镇村落' },
      { value: '亲子家庭', label: '👨‍👩‍👧‍👦 亲子家庭' }
    ],
    recommendSelectedTags: [],
    recommendStartCity: '',
    recommendPreferences: '',
    recommendResult: [],
    // 路线选项
    forceGateway: true,
    forceOrder: false,
    maxHoursOptions: [
      { value: 3, label: '3小时' },
      { value: 4, label: '4小时（推荐）' },
      { value: 5, label: '5小时' },
      { value: 6, label: '6小时' }
    ],
    maxHoursIndex: 1,
    transportOptions: [
      { value: 'auto', label: '自动' },
      { value: 'train', label: '优先火车' },
      { value: 'flight', label: '优先飞机' }
    ],
    transportIndex: 0,
    displayModeOptions: [
      { value: 'compact', label: '精简' },
      { value: 'detailed', label: '详细' }
    ],
    displayModeIndex: 0,
    destStartNode: '',
    destEndNode: '',
    route: null,
    routeCities: [],
    routeItinerary: [],
    loading: false,
    loadingText: '',
    errorMsg: ''
  },

  // 点图放大预览，同一天的图可左右滑
  previewDayImage(e) {
    const { images, url } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls: (images || []).map(p => p.url) })
  },

  openPlaybook(e) {
    const name = e.currentTarget.dataset.name
    wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 攻略搜索：输入地名 → 命中卡片
  onGuideSearchInput(e) {
    const v = e.detail.value
    this.setData({ guideSearchInput: v })
    clearTimeout(this._searchTimer)
    if (!v || !v.trim()) {
      this.setData({ guideSearchResults: [], guideSearched: false })
      return
    }
    // 防抖 300ms
    this._searchTimer = setTimeout(() => this.doGuideSearch(v.trim()), 300)
  },

  doGuideSearch(q) {
    api.searchAttractions(q).then(res => {
      const results = ((res && res.results) || []).map(r => ({
        ...r,
        thumb: r.thumb ? api.imageUrl(r.thumb) : ''
      }))
      this.setData({ guideSearchResults: results, guideSearched: true })
    }).catch(() => {
      this.setData({ guideSearchResults: [], guideSearched: true })
    })
  },

  clearGuideSearch() {
    clearTimeout(this._searchTimer)
    this.setData({ guideSearchInput: '', guideSearchResults: [], guideSearched: false })
  },

  // 点搜索结果卡片 → 跳详情页
  openSearchResult(e) {
    const name = e.currentTarget.dataset.name
    wx.navigateTo({ url: `/pages/attraction/attraction?name=${encodeURIComponent(name)}` })
  },

  // 行程里 images 的相对路径转完整 URL
  resolveItineraryImages(itinerary) {
    return (itinerary || []).map(d => {
      if (Array.isArray(d.images) && d.images.length) {
        d.images = d.images.map(p => ({ ...p, url: api.imageUrl(p.url) }))
      }
      return d
    })
  },

  onLoad() {
    this.loadRecommendCountries('欧洲')
  },

  onShow() {
    const sc = app.globalData && Array.isArray(app.globalData.selectedCities)
      ? app.globalData.selectedCities
      : []
    this.setData({ selectedCities: sc })
    if (app.globalData && app.globalData.generatedRoute) {
      const r = app.globalData.generatedRoute
      this.setData({
        route: r,
        routeCities: Array.isArray(r.cities) ? r.cities : [],
        routeItinerary: this.resolveItineraryImages(Array.isArray(r.itinerary) ? r.itinerary : [])
      })
    }
    // onShow 也调用一次，确保切换 tab 后也能加载
    if (this.data.recommendCountries.length === 0) {
      this.loadRecommendCountries('欧洲')
    }
  },

  // ---- 推荐相关 ----
  onMonthChange(e) {
    this.setData({ monthIndex: parseInt(e.detail.value) })
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  selectRecommendRegion(e) {
    const region = e.currentTarget.dataset.region
    const opt = this.data.regionOptions.find(r => r.value === region)
    this.setData({ recommendRegion: region, recommendSelectedCountries: [], recommendCountries: [] })
    this.loadRecommendCountries(opt.cn)
  },

  async loadRecommendCountries(regionCN) {
    console.log('[guide] 开始加载国家:', regionCN)
    console.log('[guide] 当前 recommendCountries:', this.data.recommendCountries)
    try {
      const res = await api.getCountries(regionCN)
      console.log('[guide] 响应:', JSON.stringify(res))
      console.log('[guide] res.success:', res.success, 'res.countries:', res.countries)
      if (res && res.success && Array.isArray(res.countries)) {
        console.log('[guide] 准备设置国家，数量:', res.countries.length)
        this.setData({ recommendCountries: res.countries }, () => {
          console.log('[guide] setData 完成，当前 recommendCountries:', this.data.recommendCountries)
        })
      } else {
        console.error('[guide] 响应格式异常:', res)
        this.setData({ recommendCountries: [] })
      }
    } catch (e) {
      console.error('[guide] 加载国家失败:', e)
      console.error('[guide] 错误详情:', JSON.stringify(e))
      this.setData({ recommendCountries: [] })
    }
  },

  toggleManualRecommendCountry(e) {
    const country = e.currentTarget.dataset.country
    const checked = e.detail.value.length > 0
    let selected = [...this.data.recommendSelectedCountries]
    const idx = selected.indexOf(country)
    if (checked && idx === -1) {
      selected.push(country)
    } else if (!checked && idx > -1) {
      selected.splice(idx, 1)
    }
    this.setData({ recommendSelectedCountries: selected })
  },

  toggleManualRecommendTag(e) {
    const tag = e.currentTarget.dataset.tag
    const checked = e.detail.value.length > 0
    let selected = [...this.data.recommendSelectedTags]
    const idx = selected.indexOf(tag)
    if (checked && idx === -1) {
      selected.push(tag)
    } else if (!checked && idx > -1) {
      selected.splice(idx, 1)
    }
    this.setData({ recommendSelectedTags: selected })
  },

  async getRecommendation() {
    const d = this.data
    const daysInput = d.recommendDays.trim ? d.recommendDays.trim() : String(d.recommendDays).trim()
    const days = daysInput ? parseInt(daysInput) : 10  // 不填默认10天
    if (daysInput && (days < 3 || days > 30)) {
      wx.showToast({ title: '天数需在3-30之间', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '正在推荐...', recommendResult: [], errorMsg: '' })

    try {
      const body = {
        mode: 'recommend',
        travel_month: d.monthOptions[d.monthIndex].value,
        duration_days: days,
        region: d.recommendRegion,
        force_gateway_departure: d.forceGateway,
        force_order: d.forceOrder,
        same_day_max_hours: d.maxHoursOptions[d.maxHoursIndex].value,
        transport_preference: d.transportOptions[d.transportIndex].value,
        options_display_mode: d.displayModeOptions[d.displayModeIndex].value
      }
      if (d.recommendSelectedCountries.length > 0) {
        body.countries = d.recommendSelectedCountries
      }
      if (d.recommendSelectedTags.length > 0) {
        body.tags = d.recommendSelectedTags
      }
      const startCity = (d.recommendStartCity || '').trim()
      if (startCity) {
        body.start_city = startCity
      }
      const prefsText = (d.recommendPreferences || '').trim()
      if (prefsText) {
        body.destinations = prefsText.split(',').map(c => c.trim()).filter(c => c)
      }

      const res = await api.generateRoute(body)
      const cities = (res.route && Array.isArray(res.route.cities)) ? res.route.cities : []
      this.setData({ loading: false, recommendResult: cities })

      if (cities.length === 0) {
        this.setData({ errorMsg: '未找到合适的推荐路线' })
      }
    } catch (err) {
      this.setData({ loading: false, errorMsg: '推荐失败' })
    }
  },

  applyRecommendation() {
    const cities = this.data.recommendResult
    if (cities.length === 0) return
    const merged = this.data.selectedCities.slice()
    cities.forEach(c => {
      if (merged.indexOf(c) === -1) merged.push(c)
    })
    this.setData({ selectedCities: merged })
    app.globalData.selectedCities = merged
    wx.showToast({ title: `已添加${cities.length}个城市`, icon: 'success' })
  },

  // ---- 模式切换 ----
  switchGuideMode(e) {
    const mode = e.currentTarget.dataset.mode
    // 「帮我推荐」不支持国内：从国内切回推荐时回落到欧洲
    if (mode === 'recommend' && this.data.recommendRegion === CN_REGION) {
      this.setData({ guideMode: mode, recommendRegion: 'Europe', isCN: false, recommendSelectedCountries: [], recommendCountries: [] })
      this.loadRecommendCountries('欧洲')
      return
    }
    this.setData({ guideMode: mode })
    if (mode === 'pick' && this.data.pickCountries.length === 0) {
      this.loadPickCountries(this.data.regionOptions.find(r => r.value === this.data.recommendRegion).cn)
    }
  },

  toggleRouteOptions() {
    this.setData({ showRouteOptions: !this.data.showRouteOptions })
  },

  // ---- 「知道去哪」模式：搜索联想（国家+城市）----
  onPickSearchInput(e) {
    const val = e.detail.value.trim()
    this.setData({ pickSearchInput: val })
    if (!val) {
      this.setData({ pickSuggestions: [] })
      return
    }
    clearTimeout(this._pickSearchTimer)
    this._pickSearchTimer = setTimeout(async () => {
      try {
        const res = await api.searchDestinations(val)
        this.setData({ pickSuggestions: Array.isArray(res.suggestions) ? res.suggestions : [] })
      } catch (err) {
        console.error('搜索失败', err)
      }
    }, 300)
  },

  selectPickSuggestion(e) {
    const item = this.data.pickSuggestions[e.currentTarget.dataset.index]
    if (!item) return
    if (item.type === 'country') {
      // 选国家：切到对应区域并展开该国城市卡片
      const opt = this.data.regionOptions.find(r => r.cn === item.region)
      this.setData({
        pickSearchInput: '',
        pickSuggestions: [],
        recommendRegion: opt ? opt.value : this.data.recommendRegion,
        pickCurrentCountry: item.name
      })
      if (opt) this.loadPickCountries(opt.cn)
      this.loadPickCities(item.name)
    } else {
      // 选城市：直接加入已选
      let list = this.data.selectedCities.slice()
      if (list.indexOf(item.name) === -1) list.push(item.name)
      this.setData({ pickSearchInput: '', pickSuggestions: [], selectedCities: list })
      app.globalData.selectedCities = list
    }
  },

  // ---- 「知道去哪」模式：自己选城（区域→国家→城市）----
  selectPickRegion(e) {
    const region = e.currentTarget.dataset.region
    const opt = this.data.regionOptions.find(r => r.value === region)
    this.setData({ recommendRegion: region, isCN: region === CN_REGION, pickCurrentCountry: '', pickCities: [], pickGroups: [], pickCountries: [] })
    this.loadPickCountries(opt.cn)
  },

  async loadPickCountries(regionCN) {
    try {
      const res = await api.getCountries(regionCN)
      this.setData({ pickCountries: (res && res.success && Array.isArray(res.countries)) ? res.countries : [] })
    } catch (e) {
      this.setData({ pickCountries: [] })
    }
  },

  selectPickCountry(e) {
    const country = e.currentTarget.dataset.country
    this.setData({ pickCurrentCountry: country })
    this.loadPickCities(country)
  },

  async loadPickCities(country) {
    const regionCN = this.data.regionOptions.find(r => r.value === this.data.recommendRegion).cn
    try {
      const res = await api.getCities(regionCN, country, 40)
      const cities = (res && res.success && Array.isArray(res.cities)) ? res.cities : []
      this.setData({ pickCities: cities, pickGroups: buildCityGroups(country, cities) })
    } catch (e) {
      this.setData({ pickCities: [], pickGroups: [] })
    }
  },

  togglePickCity(e) {
    const name = e.currentTarget.dataset.name
    let list = this.data.selectedCities.slice()
    const idx = list.indexOf(name)
    if (idx > -1) list.splice(idx, 1)
    else list.push(name)
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  removeSelectedCity(e) {
    const name = e.currentTarget.dataset.name
    const list = this.data.selectedCities.filter(c => c !== name)
    this.setData({ selectedCities: list })
    app.globalData.selectedCities = list
  },

  clearSelectedCities() {
    this.setData({ selectedCities: [] })
    app.globalData.selectedCities = []
    app.globalData.generatedRoute = null
  },

  // ---- 路线生成 ----
  onSwitchChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  onMaxHoursChange(e) {
    this.setData({ maxHoursIndex: parseInt(e.detail.value) })
  },

  onTransportChange(e) {
    this.setData({ transportIndex: parseInt(e.detail.value) })
  },

  onDisplayModeChange(e) {
    this.setData({ displayModeIndex: parseInt(e.detail.value) })
  },

  async generate() {
    if (this.data.selectedCities.length < 2) {
      wx.showToast({ title: '请至少选择2个城市', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '正在生成攻略...', route: null, errorMsg: '' })

    try {
      const res = await api.generateRoute({
        mode: 'destination',
        cities: this.data.selectedCities,
        region: this.data.recommendRegion,
        force_gateway_departure: this.data.forceGateway,
        force_order: this.data.forceOrder,
        same_day_max_hours: this.data.maxHoursOptions[this.data.maxHoursIndex].value,
        transport_preference: this.data.transportOptions[this.data.transportIndex].value,
        options_display_mode: this.data.displayModeOptions[this.data.displayModeIndex].value,
        start_node: this.data.destStartNode.trim() || null,
        end_node: this.data.destEndNode.trim() || null
      })

      const route = res.route || null
      const routeCities = (route && Array.isArray(route.cities)) ? route.cities : []
      const routeItinerary = this.resolveItineraryImages((route && Array.isArray(route.itinerary)) ? route.itinerary : [])
      app.globalData.generatedRoute = route
      this.setData({ route, routeCities, routeItinerary, loading: false })
    } catch (err) {
      this.setData({ loading: false, errorMsg: '生成失败' })
    }
  },

  // ---- 国内：不生成路线，直接把已选城市按顺序打包去发帖 ----
  goFindCompanionFromCities() {
    const cities = this.data.selectedCities.slice()
    if (cities.length === 0) {
      wx.showToast({ title: '请先选择城市', icon: 'none' })
      return
    }
    app.globalData.generatedRoute = {
      route_type: 'cities_only',
      cities: cities,
      city_count: cities.length,
      total_days: 0,
      itinerary: []
    }
    app.globalData.selectedCities = cities
    app.globalData.routeFromGuide = true
    wx.navigateTo({ url: '/pages/index/index' })
  },

  // ---- 打通：带着已生成的路线去发布找搭子 ----
  goFindCompanion() {
    const route = this.data.route
    if (!route) {
      wx.showToast({ title: '请先生成攻略', icon: 'none' })
      return
    }
    // 标记来自攻略，发布页 onShow 据此填充城市，避免被覆盖
    app.globalData.generatedRoute = route
    app.globalData.selectedCities = Array.isArray(route.cities) ? route.cities.slice() : []
    app.globalData.routeFromGuide = true
    wx.navigateTo({ url: '/pages/index/index' })
  }
})
