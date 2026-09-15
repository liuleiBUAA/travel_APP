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
  // ---- 国内：33 个省级行政区（省/自治区/直辖市/特区各自独立，不合并）----
  //      地点少的省不设分组，前端自动扁平展示
  '北京': [
    { icon: '🏙', title: '北京（全城）', cities: ['北京'] },
    { icon: '📍', title: '东城区', cities: ['故宫博物院', '天安门广场', '天坛', '雍和宫', '国子监·孔庙', '南锣鼓巷', '前门大街', '中国国家博物馆'] },
    { icon: '📍', title: '西城区', cities: ['北海公园', '景山公园', '什刹海', '恭王府', '北京动物园', '先农坛·古代建筑博物馆', '白塔寺'] },
    { icon: '📍', title: '朝阳区', cities: ['798艺术区', '朝阳公园', '奥林匹克公园·鸟巢水立方', '751园区', '红砖美术馆', '蓝色港湾'] },
    { icon: '📍', title: '海淀区', cities: ['颐和园', '圆明园', '香山公园', '国家植物园北园', '清华大学·北京大学校园', '凤凰岭', '紫竹院公园'] },
    { icon: '📍', title: '丰台区', cities: ['卢沟桥·宛平城', '中国人民抗日战争纪念馆', '北京世界公园', '北京汽车博物馆', '北京园博园', '北宫国家森林公园'] },
    { icon: '📍', title: '石景山区', cities: ['首钢园', '石景山游乐园', '八大处公园', '法海寺壁画', '模式口历史文化街区'] },
    { icon: '📍', title: '门头沟区', cities: ['潭柘寺', '戒台寺', '东灵山', '百花山', '妙峰山', '爨底下村', '京西古道', '双龙峡'] },
    { icon: '📍', title: '房山区', cities: ['周口店北京人遗址', '云居寺', '十渡', '石花洞', '上方山国家森林公园', '坡峰岭', '银狐洞'] },
    { icon: '📍', title: '通州区', cities: ['北京环球影城', '大运河森林公园', '燃灯塔·西海子公园', '张家湾古镇', '城市绿心森林公园', '宋庄艺术区'] },
    { icon: '📍', title: '顺义区', cities: ['奥林匹克水上公园', '汉石桥湿地', '中国民航博物馆', '焦庄户地道战遗址', '龙湾屯浅山'] },
    { icon: '📍', title: '大兴区', cities: ['北京野生动物园', '南海子麋鹿苑', '大兴国际机场航站楼', '庞各庄万亩梨园', '团河行宫遗址'] },
    { icon: '📍', title: '昌平区', cities: ['明十三陵', '居庸关长城', '十三陵水库', '银山塔林', '蟒山国家森林公园', '中国航空博物馆', '虎峪'] },
    { icon: '📍', title: '平谷区', cities: ['金海湖', '石林峡', '京东大峡谷', '京东大溶洞', '丫髻山', '渔阳滑雪场'] },
    { icon: '📍', title: '怀柔区', cities: ['慕田峪长城', '箭扣长城', '雁栖湖', '红螺寺', '白河湾', '青龙峡', '神堂峪', '黄花城水长城', '喇叭沟门原始森林'] },
    { icon: '📍', title: '密云区', cities: ['古北水镇', '司马台长城', '云蒙山', '密云水库', '黑龙潭', '桃源仙谷', '清凉谷', '雾灵山'] },
    { icon: '📍', title: '延庆区', cities: ['八达岭长城', '龙庆峡', '玉渡山', '野鸭湖湿地', '北京世园公园', '松山自然保护区', '古崖居', '百里山水画廊'] },
  ],
  '上海': [
    { icon: '🏙', title: '上海（全城）', cities: ['上海'] },
    { icon: '📍', title: '黄浦区', cities: ['外滩', '豫园·城隍庙', '新天地', '田子坊', '思南公馆', '上海博物馆', '南京路步行街', '中共一大会址'] },
    { icon: '📍', title: '徐汇区', cities: ['武康路·衡复风貌区', '龙华寺', '西岸·龙美术馆', '油罐艺术中心', '上海植物园', '徐家汇书院', '宋庆龄故居'] },
    { icon: '📍', title: '长宁区', cities: ['上海动物园', '中山公园', '愚园路风貌街区', '新华路老洋房', '刘海粟美术馆'] },
    { icon: '📍', title: '静安区', cities: ['静安寺', '玉佛禅寺', '南京西路风貌区', '上海自然博物馆', '静安雕塑公园', '张园', '四行仓库抗战纪念馆'] },
    { icon: '📍', title: '普陀区', cities: ['M50创意园', '长风公园', '苏州河普陀段步道', '真如寺', '桃浦中央绿地'] },
    { icon: '📍', title: '虹口区', cities: ['外白渡桥', '多伦路文化名人街', '鲁迅公园·鲁迅故居', '1933老场坊', '犹太难民纪念馆', '北外滩滨江', '上海邮政博物馆'] },
    { icon: '📍', title: '杨浦区', cities: ['杨浦滨江·绿之丘', '复旦大学校园', '同济大学校园', '共青国家森林公园', '上海国际时尚中心', '江湾体育场'] },
    { icon: '📍', title: '闵行区', cities: ['七宝老街', '召稼楼古镇', '闵行体育公园', '锦江乐园', '交大闵行樱花大道', '韩湘水博园'] },
    { icon: '📍', title: '宝山区', cities: ['吴淞炮台湾湿地公园', '上海玻璃博物馆', '顾村公园', '宝山寺', '淞沪抗战纪念馆', '罗店古镇'] },
    { icon: '📍', title: '嘉定区', cities: ['嘉定古城·州桥老街', '嘉定孔庙', '秋霞圃', '古猗园·南翔', '上海汽车博物馆·安亭', '上海国际赛车场'] },
    { icon: '📍', title: '浦东新区', cities: ['上海迪士尼度假区', '东方明珠', '上海中心大厦观光厅', '上海海洋水族馆', '上海科技馆', '上海天文馆·临港', '滴水湖', '上海野生动物园', '陆家嘴滨江·浦东美术馆', '新场古镇'] },
    { icon: '📍', title: '金山区', cities: ['金山城市沙滩', '金山三岛', '枫泾古镇', '中国农民画村', '廊下郊野公园'] },
    { icon: '📍', title: '松江区', cities: ['佘山国家森林公园', '深坑酒店', '广富林文化遗址', '醉白池', '方塔园', '上海欢乐谷', '辰山植物园', '泰晤士小镇'] },
    { icon: '📍', title: '青浦区', cities: ['朱家角古镇', '金泽古镇', '练塘古镇', '青浦大观园', '东方绿舟', '淀山湖', '青西郊野公园'] },
    { icon: '📍', title: '奉贤区', cities: ['碧海金沙', '海湾国家森林公园', '上海之鱼·九棵树', '庄行古镇', '申隆生态园'] },
    { icon: '📍', title: '崇明区', cities: ['崇明东滩湿地', '东平国家森林公园', '西沙湿地·明珠湖', '长兴岛郊野公园', '瀛东村'] },
  ],
  '天津': [
    { icon: '🏙', title: '天津（全城）', cities: ['天津'] },
    { icon: '📍', title: '和平区', cities: ['五大道风貌区', '瓷房子', '张学良故居', '西开教堂', '津湾广场'] },
    { icon: '📍', title: '河东区', cities: ['天津规划展览馆', '棉3创意街区', '第二工人文化宫'] },
    { icon: '📍', title: '河西区', cities: ['天津博物馆', '天津文化中心', '天塔湖', '梅江公园'] },
    { icon: '📍', title: '南开区', cities: ['古文化街·天后宫', '天津鼓楼', '广东会馆', '水上公园', '天津动物园', '周恩来邓颖超纪念馆', '天津文庙'] },
    { icon: '📍', title: '河北区', cities: ['天津之眼摩天轮', '意式风情区', '望海楼教堂', '大悲禅院', '北宁公园'] },
    { icon: '📍', title: '红桥区', cities: ['平津战役纪念馆', '桃花堤', '吕祖堂', '西沽公园'] },
    { icon: '📍', title: '滨海新区', cities: ['滨海图书馆', '国家海洋博物馆', '航母主题公园', '东疆湾沙滩', '方特欢乐世界', '大沽口炮台遗址'] },
    { icon: '📍', title: '东丽区', cities: ['东丽湖温泉度假区', '天津郊野公园'] },
    { icon: '📍', title: '西青区', cities: ['杨柳青古镇·石家大院', '杨柳青年画馆', '精武门中华武林园', '热带植物观光园'] },
    { icon: '📍', title: '津南区', cities: ['小站练兵园', '葛沽古镇', '海河故道公园'] },
    { icon: '📍', title: '北辰区', cities: ['北辰郊野公园', '天穆清真南大寺'] },
    { icon: '📍', title: '武清区', cities: ['天津绿博园', '武清南湖·永定塔', '北运河郊野公园'] },
    { icon: '📍', title: '宝坻区', cities: ['潮白河湿地公园', '京津新城温泉', '宝坻广济寺'] },
    { icon: '📍', title: '静海区', cities: ['团泊湖景区', '静海林海', '西双塘生态区'] },
    { icon: '📍', title: '蓟州区', cities: ['盘山', '黄崖关长城', '独乐寺', '九山顶', '梨木台', '八仙山', '翠屏湖', '蓟州溶洞', '郭家沟'] },
    { icon: '📍', title: '宁河区', cities: ['七里海湿地', '天尊阁'] },
  ],
  '重庆': [
    { icon: '🏙', title: '重庆（全城）', cities: ['重庆'] },
    { icon: '📍', title: '渝中区', cities: ['洪崖洞', '解放碑', '李子坝轻轨穿楼', '鹅岭二厂', '十八梯', '山城巷', '湖广会馆', '长江索道'] },
    { icon: '📍', title: '江北区', cities: ['观音桥', '江北嘴中央公园·大剧院', '重庆科技馆', '鸿恩寺森林公园', '铁山坪森林公园'] },
    { icon: '📍', title: '南岸区', cities: ['南山一棵树观景台', '南山植物园', '弹子石老街', '龙门浩老街', '重庆抗战遗址博物馆', '涂山寺'] },
    { icon: '📍', title: '沙坪坝区', cities: ['磁器口古镇', '白公馆·渣滓洞', '歌乐山森林公园', '重庆大学老校区'] },
    { icon: '📍', title: '九龙坡区', cities: ['黄桷坪涂鸦街', '建川博物馆聚落', '华岩寺', '重庆动物园', '彩云湖湿地'] },
    { icon: '📍', title: '渝北区', cities: ['照母山森林公园', '重庆中央公园', '龙兴古镇', '两江国际影视城', '统景温泉', '重庆园博园'] },
    { icon: '📍', title: '大渡口区', cities: ['重庆工业博物馆', '马桑溪古镇', '中华美德公园'] },
    { icon: '📍', title: '北碚区', cities: ['缙云山', '金刀峡', '北温泉公园', '偏岩古镇'] },
    { icon: '📍', title: '巴南区', cities: ['丰盛古镇', '东温泉', '南温泉', '圣灯山', '汉海海洋公园'] },
    { icon: '📍', title: '武隆区', cities: ['天生三桥', '仙女山', '芙蓉洞', '龙水峡地缝', '白马山'] },
    { icon: '📍', title: '大足区', cities: ['大足石刻', '龙水湖', '玉龙山', '昌州古城'] },
    { icon: '📍', title: '江津区', cities: ['四面山', '中山古镇', '白沙古镇'] },
    { icon: '📍', title: '万盛经开区', cities: ['黑山谷', '龙鳞石海', '奥陶纪主题公园', '板辽金沙滩'] },
    { icon: '📍', title: '南川区', cities: ['金佛山', '山王坪', '神龙峡', '黎香湖'] },
    { icon: '📍', title: '彭水县', cities: ['阿依河', '蚩尤九黎城', '摩围山', '乌江画廊'] },
    { icon: '📍', title: '黔江区', cities: ['濯水古镇', '蒲花暗河', '阿蓬江神龟峡', '小南海'] },
    { icon: '📍', title: '酉阳县', cities: ['龚滩古镇', '酉阳桃花源', '龙潭古镇', '叠石花谷'] },
    { icon: '📍', title: '巫山县', cities: ['巫山小三峡', '神女峰·神女天路', '文峰观', '当阳大峡谷'] },
    { icon: '📍', title: '奉节县', cities: ['白帝城·瞿塘峡', '小寨天坑', '天井峡地缝', '三峡之巅'] },
    { icon: '📍', title: '涪陵区', cities: ['白鹤梁水下博物馆', '武陵山大裂谷', '816地下核工程', '大木花谷'] },
    { icon: '📍', title: '永川区', cities: ['松溉古镇', '茶山竹海', '乐和乐都'] },
    { icon: '📍', title: '合川区', cities: ['钓鱼城', '涞滩古镇', '龙多山'] },
    { icon: '📍', title: '石柱县', cities: ['黄水国家森林公园', '千野草场', '毕兹卡绿宫'] },
    { icon: '📍', title: '丰都县', cities: ['丰都名山', '南天湖', '雪玉洞'] },
    { icon: '📍', title: '云阳县', cities: ['龙缸·云端廊桥', '张飞庙'] },
    { icon: '📍', title: '长寿区', cities: ['长寿湖', '长寿古镇', '菩提古镇'] },
  ],
  '香港': [
    { icon: '🏙', title: '港岛·九龙', cities: ['香港', '维多利亚港·尖沙咀', '太平山顶', '中环·兰桂坊', '铜锣湾', '旺角·油麻地'] },
    { icon: '🎡', title: '主题乐园', cities: ['香港迪士尼乐园', '海洋公园', '大屿山·昂坪360'] },
    { icon: '🏝', title: '离岛·郊野', cities: ['南丫岛', '赤柱', '西贡·万宜水库', '大澳渔村', '麦理浩径·龙脊'] },
  ],
  '澳门': [
    { icon: '⛪', title: '澳门半岛', cities: ['澳门', '大三巴牌坊', '议事亭前地', '妈阁庙', '澳门塔', '渔人码头·澳门科学馆'] },
    { icon: '🎰', title: '氹仔·路环', cities: ['金光大道·威尼斯人', '氹仔官也街', '龙环葡韵', '路环·黑沙海滩'] },
  ],
  '吉林': [
    { icon: '🏙', title: '长春·吉林市', cities: ['长春', '净月潭·长春', '伪满皇宫', '吉林市·松花湖', '雾凇岛', '北大湖滑雪场'] },
    { icon: '🏔', title: '长白山·东部', cities: ['长白山', '二道白河镇', '望天鹅峡谷', '集安', '六鼎山·敦化', '防川·珲春'] },
    { icon: '🦢', title: '西部草原湖泊', cities: ['查干湖'] },
  ],
  '辽宁': [
    { icon: '🏖', title: '大连·滨海', cities: ['大连', '星海广场·大连', '金石滩', '旅顺口', '兴城', '笔架山·锦州', '红海滩·盘锦'] },
    { icon: '⛰', title: '辽东山区', cities: ['丹东·鸭绿江', '本溪水洞', '关门山·本溪', '老边沟·本溪', '五女山·桓仁', '绿江村·宽甸'] },
    { icon: '🏯', title: '沈阳·辽中', cities: ['沈阳', '千山·鞍山'] },
  ],
  '宁夏': [
    { icon: '🏯', title: '银川·贺兰山', cities: ['银川', '西夏王陵', '贺兰山·镇北堡', '贺兰山岩画', '沙湖'] },
    { icon: '🏜', title: '中卫·沙漠黄河', cities: ['沙坡头·中卫', '腾格里·通湖草原', '水洞沟', '黄沙古渡', '青铜峡黄河大峡谷'] },
    { icon: '⛰', title: '固原·六盘山', cities: ['六盘山', '须弥山石窟·固原', '火石寨·西吉'] },
  ],
  '山西': [
    { icon: '🏮', title: '晋中·平遥', cities: ['太原', '平遥古城', '王家大院', '乔家大院', '绵山'] },
    { icon: '🛕', title: '晋北·大同五台', cities: ['云冈石窟·大同', '悬空寺', '恒山', '五台山', '雁门关'] },
    { icon: '🧗', title: '晋南·晋西', cities: ['碛口古镇', '鹳雀楼·永济', '洪洞大槐树'] },
  ],
  '内蒙古': [
    { icon: '🌲', title: '呼伦贝尔·大兴安岭', cities: ['呼伦贝尔', '海拉尔', '额尔古纳', '满洲里', '根河·敖鲁古雅', '阿尔山'] },
    { icon: '🐎', title: '锡林郭勒·乌兰布统', cities: ['乌兰布统', '锡林郭勒草原', '希拉穆仁草原', '克什克腾·阿斯哈图'] },
    { icon: '🏜', title: '河套·库布齐', cities: ['呼和浩特', '库布齐响沙湾', '鄂尔多斯', '包头·五当召'] },
    { icon: '🌵', title: '阿拉善·额济纳', cities: ['额济纳', '阿拉善·巴丹吉林沙漠'] },
  ],
  '浙江': [
    { icon: '🌉', title: '杭嘉湖·绍兴', cities: ['杭州西湖', '千岛湖', '莫干山', '乌镇', '西塘', '南浔', '绍兴'] },
    { icon: '🏝', title: '浙东·舟山海岛', cities: ['宁波', '普陀山', '东极岛', '嵊泗列岛', '象山石浦'] },
    { icon: '⛰', title: '浙南山水', cities: ['温州', '雁荡山', '楠溪江', '缙云仙都'] },
    { icon: '📍', title: '杭州·上城区', cities: ['河坊街', '南宋御街', '吴山城隍阁', '南宋德寿宫遗址', '湖滨步行街', '白塔公园'] },
    { icon: '📍', title: '杭州·拱墅区', cities: ['拱宸桥·桥西历史街区', '京杭大运河夜游', '小河直街', '香积寺', '半山国家森林公园', '大运河亚运公园'] },
    { icon: '📍', title: '杭州·西湖区', cities: ['杭州西湖', '灵隐寺·飞来峰', '西溪国家湿地公园', '龙井村·九溪十八涧', '中国茶叶博物馆', '宋城', '云栖竹径'] },
    { icon: '📍', title: '杭州·滨江区', cities: ['白马湖', '中国网络作家村', '杭州奥体中心', '闻涛路樱花跑道', '冠山公园'] },
    { icon: '📍', title: '杭州·萧山区', cities: ['湘湖', '跨湖桥遗址博物馆', '杭州乐园', '东方文化园', '江寺公园'] },
    { icon: '📍', title: '杭州·余杭区', cities: ['良渚古城遗址公园', '良渚博物院', '径山寺·径山花海', '双溪竹海漂流', '大径山乡村公园'] },
    { icon: '📍', title: '杭州·临平区', cities: ['塘栖古镇·广济桥', '超山风景区', '临平山公园', '丁山湖', '塘栖水北街'] },
    { icon: '📍', title: '杭州·钱塘区', cities: ['钱塘江观潮点', '金沙湖', '江东湿地', '下沙沿江景观带'] },
    { icon: '📍', title: '杭州·富阳区', cities: ['龙门古镇', '富春桃源', '黄公望隐居地', '鹳山·郁达夫故居', '新沙岛', '永安山'] },
    { icon: '📍', title: '杭州·临安区', cities: ['天目山·禅源寺', '大明山', '浙西大峡谷', '太湖源', '青山湖', '河桥古镇', '指南村', '湍口温泉'] },
    { icon: '📍', title: '杭州·桐庐县', cities: ['瑶琳仙境', '严子陵钓台', '垂云通天河', '大奇山', '深澳古村', '芦茨湾'] },
    { icon: '📍', title: '杭州·淳安县', cities: ['千岛湖', '文渊狮城', '芹川古村', '下姜村', '千岛湖石林', '环湖绿道'] },
    { icon: '📍', title: '杭州·建德市', cities: ['新安江七里扬帆', '大慈岩·新叶古村', '梅城古镇', '灵栖洞', '新安江夜游'] },
  ],
  '福建': [
    { icon: '🏝', title: '厦漳泉', cities: ['厦门', '鼓浪屿', '泉州', '南靖云水谣土楼', '永定土楼', '东山岛'] },
    { icon: '🍃', title: '闽北·武夷', cities: ['武夷山', '泰宁大金湖', '三明格氏栲'] },
    { icon: '📷', title: '闽东·福州宁德', cities: ['福州三坊七巷', '平潭岛', '霞浦滩涂', '太姥山', '湄洲岛·莆田'] },
  ],
  '山东': [
    { icon: '🏖', title: '胶东海滨', cities: ['青岛', '崂山', '威海·刘公岛', '蓬莱·烟台', '荣成天鹅湖', '日照'] },
    { icon: '⛰', title: '鲁中·济南泰山', cities: ['济南', '泰山', '淄博', '沂蒙山'] },
    { icon: '🏯', title: '鲁南·曲阜', cities: ['曲阜三孔', '台儿庄古城', '微山湖'] },
  ],
  '河南': [
    { icon: '🛕', title: '洛阳·郑州', cities: ['郑州', '开封', '洛阳龙门石窟', '老君山', '嵩山少林寺'] },
    { icon: '🏞', title: '太行山水', cities: ['云台山', '郭亮村·万仙山', '龙潭大峡谷', '尧山'] },
    { icon: '🏺', title: '豫北·豫南', cities: ['安阳殷墟', '鸡公山·信阳'] },
  ],
  '湖北': [
    { icon: '🌉', title: '武汉·鄂东', cities: ['武汉', '黄鹤楼', '荆州古城', '襄阳古城', '武当山'] },
    { icon: '🏞', title: '鄂西·恩施神农架', cities: ['恩施大峡谷', '清江画廊', '神农架', '三峡大坝·宜昌'] },
  ],
  '湖南': [
    { icon: '⛰', title: '张家界·湘西', cities: ['张家界', '天门山', '袁家界', '凤凰古城', '芙蓉镇', '矮寨大桥'] },
    { icon: '🏙', title: '长沙·湘中南', cities: ['长沙', '南岳衡山', '崀山', '岳阳楼·洞庭湖', '韶山'] },
  ],
  '广东': [
    { icon: '🏙', title: '广深珠', cities: ['广州', '深圳', '珠海'] },
    { icon: '🍜', title: '潮汕', cities: ['潮州', '汕头南澳岛', '揭阳'] },
    { icon: '🏖', title: '粤西海岸', cities: ['海陵岛·阳江', '双月湾·惠州', '湛江', '茂名浪漫海岸'] },
    { icon: '⛰', title: '粤北山水', cities: ['丹霞山·韶关', '开平碉楼', '南昆山'] },
    { icon: '📍', title: '深圳·福田区', cities: ['莲花山公园', '深圳博物馆·市民中心', '香蜜公园', '福田红树林生态公园', '深圳中心公园'] },
    { icon: '📍', title: '深圳·罗湖区', cities: ['东门老街', '梧桐山主入口', '仙湖植物园·弘法寺', '洪湖公园', '地王大厦观景台'] },
    { icon: '📍', title: '深圳·南山区', cities: ['世界之窗', '深圳欢乐谷', '锦绣中华·民俗文化村', '深圳湾公园·人才公园', '蛇口海上世界', '南头古城', '大沙河生态长廊'] },
    { icon: '📍', title: '深圳·宝安区', cities: ['凤凰山森林公园', '宝安欢乐港湾·灯塔图书馆', '宝安海滨文化公园', '绮云书室'] },
    { icon: '📍', title: '深圳·龙岗区', cities: ['大芬油画村', '甘坑客家小镇', '鹤湖新居', '龙园', '深圳大运中心'] },
    { icon: '📍', title: '深圳·龙华区', cities: ['观澜湖休闲旅游区', '观澜古墟', '中国版画博物馆', '羊台山森林公园'] },
    { icon: '📍', title: '深圳·盐田区', cities: ['大梅沙海滨公园', '小梅沙', '东部华侨城', '中英街', '盐田海滨栈道'] },
    { icon: '📍', title: '深圳·坪山区', cities: ['大万世居', '坪山美术馆·坪山大剧院', '马峦山郊野公园', '聚龙山生态公园'] },
    { icon: '📍', title: '深圳·光明区', cities: ['光明农场大观园', '光明小镇欢乐田园', '虹桥公园', '大顶岭绿道'] },
    { icon: '📍', title: '深圳·大鹏新区', cities: ['大鹏所城', '较场尾', '杨梅坑', '西涌沙滩', '桔钓沙', '七娘山', '玫瑰海岸', '南澳渔村'] },
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
  '四川': [
    { icon: '🐼', title: '成都平原·川东南', cities: ['成都', '都江堰·青城山', '乐山大佛', '峨眉山', '阆中古城', '剑门关·广元', '宜宾蜀南竹海', '自贡'] },
    { icon: '🏔', title: '川北·阿坝', cities: ['九寨沟', '黄龙', '若尔盖草原', '四姑娘山', '毕棚沟·理县'] },
    { icon: '🏕', title: '川西·甘孜', cities: ['丹巴甲居藏寨', '色达', '稻城亚丁', '新都桥', '海螺沟', '康定·塔公草原'] },
    { icon: '📍', title: '成都·锦江区', cities: ['春熙路·太古里', '大慈寺', '望江楼公园', '三圣花乡', '白鹭湾湿地'] },
    { icon: '📍', title: '成都·青羊区', cities: ['宽窄巷子', '杜甫草堂', '金沙遗址博物馆', '文殊院', '青羊宫', '人民公园·鹤鸣茶社', '四川博物院', '浣花溪公园'] },
    { icon: '📍', title: '成都·金牛区', cities: ['成都欢乐谷', '露天音乐公园', '成都永陵博物馆', '天府艺术公园'] },
    { icon: '📍', title: '成都·武侯区', cities: ['武侯祠博物馆', '锦里古街', '铁像寺水街', '天府芙蓉园'] },
    { icon: '📍', title: '成都·成华区', cities: ['成都大熊猫繁育研究基地', '东郊记忆', '昭觉寺', '成都动物园', '成都自然博物馆'] },
    { icon: '📍', title: '成都·龙泉驿区', cities: ['洛带古镇', '龙泉山丹景台', '桃花故里', '明蜀王陵'] },
    { icon: '📍', title: '成都·青白江区', cities: ['凤凰湖景区', '城厢天府文化古镇', '福洪杏花村'] },
    { icon: '📍', title: '成都·新都区', cities: ['宝光寺', '升庵桂湖公园', '漫花庄园', '天府沸腾小镇'] },
    { icon: '📍', title: '成都·温江区', cities: ['国色天香乐园', '幸福田园', '鲁家滩湿地', '陈家桅杆'] },
    { icon: '📍', title: '成都·双流区', cities: ['黄龙溪古镇', '棠湖公园', '空港中央公园', '永安湖森林公园'] },
    { icon: '📍', title: '成都·郫都区', cities: ['三道堰古镇', '农科村', '战旗村', '望丛祠', '川菜博物馆'] },
    { icon: '📍', title: '成都·新津区', cities: ['花舞人间', '新津老君山', '观音寺明代壁画', '白鹤滩湿地', '斑竹林'] },
    { icon: '📍', title: '成都·都江堰市', cities: ['都江堰水利工程', '青城山', '灌县古城', '虹口漂流', '熊猫谷', '龙池森林公园'] },
    { icon: '📍', title: '成都·彭州市', cities: ['白鹿镇', '龙门山银厂沟', '丹景山', '九峰山'] },
    { icon: '📍', title: '成都·邛崃市', cities: ['平乐古镇', '邛崃天台山', '竹溪湖', '石笋山'] },
    { icon: '📍', title: '成都·崇州市', cities: ['街子古镇', '元通古镇', '鸡冠山', '罨画池', '道明竹艺村'] },
    { icon: '📍', title: '成都·金堂县', cities: ['五凤溪古镇', '云顶石城·慈云寺', '栖贤桃花沟'] },
    { icon: '📍', title: '成都·大邑县', cities: ['西岭雪山', '安仁古镇·刘氏庄园', '新场古镇', '花水湾温泉', '鹤鸣山'] },
    { icon: '📍', title: '成都·蒲江县', cities: ['明月村', '朝阳湖', '石象湖', '成佳茶乡'] },
    { icon: '📍', title: '成都·简阳市', cities: ['三岔湖', '龙泉湖', '石桥老街'] },
  ],
  '贵州': [
    { icon: '🏙', title: '贵阳及周边', cities: ['贵阳', '青岩古镇', '织金洞'] },
    { icon: '💧', title: '黔南·安顺', cities: ['黄果树瀑布', '荔波小七孔', '安顺屯堡'] },
    { icon: '🪘', title: '黔东南', cities: ['西江千户苗寨', '镇远古城', '肇兴侗寨', '加榜梯田', '梵净山'] },
    { icon: '🍶', title: '黔北·遵义赤水', cities: ['遵义', '赤水丹霞', '四洞沟'] },
    { icon: '⛰', title: '黔西南', cities: ['万峰林·兴义', '马岭河峡谷'] },
  ],
  '云南': [
    { icon: '🌺', title: '昆明·滇中', cities: ['昆明', '石林', '抚仙湖', '东川红土地', '罗平油菜花'] },
    { icon: '🏯', title: '大理·丽江', cities: ['大理', '双廊', '沙溪古镇', '丽江', '束河古镇', '玉龙雪山', '泸沽湖'] },
    { icon: '🏔', title: '迪庆·香格里拉', cities: ['香格里拉', '普达措', '虎跳峡', '梅里雪山·雨崩', '怒江·丙中洛'] },
    { icon: '♨️', title: '滇西·腾冲', cities: ['腾冲', '和顺古镇', '瑞丽'] },
    { icon: '🌴', title: '滇南·西双版纳', cities: ['西双版纳', '普洱'] },
    { icon: '🌾', title: '滇东南·红河', cities: ['元阳梯田', '建水古城', '普者黑'] },
  ],
  '西藏': [
    { icon: '🛕', title: '拉萨及周边', cities: ['拉萨', '纳木错', '羊卓雍措', '山南'] },
    { icon: '🌲', title: '林芝·藏东南', cities: ['林芝', '雅鲁藏布大峡谷', '巴松措', '鲁朗林海', '南迦巴瓦·索松村', '然乌湖', '米堆冰川', '墨脱', '昌都'] },
    { icon: '🏔', title: '日喀则·珠峰', cities: ['日喀则', '珠峰大本营', '吉隆沟'] },
    { icon: '🕉', title: '阿里·那曲', cities: ['那曲', '色林错', '阿里·冈仁波齐', '玛旁雍错', '扎达土林·古格'] },
  ],
  '陕西': [
    { icon: '🏯', title: '西安·关中', cities: ['西安', '兵马俑', '华山', '法门寺·宝鸡', '乾陵', '太白山'] },
    { icon: '🟤', title: '陕北', cities: ['延安', '壶口瀑布', '靖边波浪谷', '榆林'] },
    { icon: '🌿', title: '陕南', cities: ['汉中', '华阳古镇'] },
  ],
  '甘肃': [
    { icon: '🐪', title: '河西走廊·敦煌张掖', cities: ['兰州', '敦煌', '敦煌雅丹·玉门关', '嘉峪关', '张掖七彩丹霞', '马蹄寺', '山丹军马场', '武威', '黄河石林·白银'] },
    { icon: '⛰', title: '甘南·陇东南', cities: ['天水·麦积山', '崆峒山·平凉', '甘南·扎尕那', '郎木寺', '夏河·拉卜楞寺', '官鹅沟'] },
  ],
  '青海': [
    { icon: '🏞', title: '西宁·环湖', cities: ['西宁', '塔尔寺', '门源油菜花', '祁连·卓尔山', '阿咪东索', '青海湖', '茶卡盐湖'] },
    { icon: '🧂', title: '柴达木·戈壁', cities: ['翡翠湖·大柴旦', '察尔汗盐湖', '格尔木', '冷湖·火星营地'] },
  ],
  '新疆': [
    { icon: '🏙', title: '乌鲁木齐及周边', cities: ['乌鲁木齐', '天山天池', '天山大峡谷', '江布拉克·奇台'] },
    { icon: '🏔', title: '北疆·喀纳斯阿勒泰', cities: ['喀纳斯·禾木', '白哈巴', '五彩滩·布尔津', '可可托海', '白沙湖·哈巴河', '阿勒泰'] },
    { icon: '🌾', title: '伊犁·赛里木湖', cities: ['伊宁·伊犁河谷', '伊犁·那拉提', '喀拉峻', '唐布拉', '昭苏', '果子沟', '赛里木湖', '独库公路'] },
    { icon: '🐎', title: '巴州·巴音布鲁克', cities: ['巴音布鲁克', '博斯腾湖', '库尔勒', '罗布人村寨'] },
    { icon: '🕌', title: '南疆·喀什帕米尔', cities: ['库车大峡谷', '温宿大峡谷·托木尔', '阿克苏', '喀什', '帕米尔·塔县', '和田', '泽普金湖杨'] },
    { icon: '🏜', title: '吐鲁番·克拉玛依', cities: ['吐鲁番', '魔鬼城·乌尔禾', '克拉玛依', '塔克拉玛干沙漠公路'] },
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
      // 国内一个省的地点全列（北京/新疆等已超 40），境外沿用 40
      const res = await api.getCities(regionCN, country, regionCN === '国内' ? 200 : 40)
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
