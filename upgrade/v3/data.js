export const SAVE_KEY='ai-dnd-realms:v3';
export const SAVE_VERSION=3;
export const STAT_NAMES=['might','agility','mind','will','endurance','perception','charisma','luck'];
export const BACKGROUNDS={
  wanderer:{label:'Wanderer',talents:{ironWill:1},reputation:{FreeMerchants:5}},
  thief:{label:'Former Thief',talents:{quickHands:2},reputation:{VeiledCourt:20,Wardens:-10}},
  scholar:{label:'Scholar',talents:{arcaneEdge:2},reputation:{FreeMerchants:10}},
  soldier:{label:'Ex-Soldier',talents:{ironWill:2},reputation:{Wardens:15}}
};
export const ITEMS={
  'rust-sword':{id:'rust-sword',name:'Rustbound Sword',type:'weapon',power:4,slot:'mainHand'},
  'moonleaf':{id:'moonleaf',name:'Moonleaf Tonic',type:'consumable',heal:8},
  'wardens-shield':{id:'wardens-shield',name:"Warden's Shield",type:'armor',armor:3,slot:'offHand'},
  'goblin-fang':{id:'goblin-fang',name:"Goblin King's Fang",type:'weapon',power:7,slot:'mainHand'},
  'iron-ore':{id:'iron-ore',name:'Iron Ore',type:'material'},
  'old-key':{id:'old-key',name:'Old Gate Key',type:'quest'}
};
export const ABILITIES={
  strike:{id:'strike',name:'Strike',cost:0,type:'damage',dice:'1d6',stat:'might'},
  guard:{id:'guard',name:'Guard',cost:2,type:'defend',armor:4,turns:1},
  fireball:{id:'fireball',name:'Fireball',cost:5,type:'damage',dice:'2d6',stat:'mind',status:'burning'},
  firstAid:{id:'firstAid',name:'First Aid',cost:4,type:'heal',dice:'1d8',stat:'will'}
};
export const ENEMIES={
  revenant:{id:'revenant',name:'Revenant Scout',hp:22,attack:4,armor:2,dc:13,xp:35,loot:['moonleaf','iron-ore']},
  goblin:{id:'goblin',name:'Goblin Raider',hp:18,attack:3,armor:1,dc:11,xp:30,loot:['iron-ore','goblin-fang']},
  warden:{id:'warden',name:'Rogue Warden',hp:30,attack:5,armor:4,dc:14,xp:50,loot:['wardens-shield']}
};
export const QUESTS={
  crossroads:{id:'crossroads',name:'Whispers at the Crossroads',description:'Learn why the crossroads has fallen silent.',objectives:[{id:'investigate',type:'DISCOVER',target:'crossroads_omen',label:'Investigate the strange omen',required:1},{id:'survive',type:'SURVIVE',target:'encounter',label:'Survive the first danger',required:1}],reward:{xp:80,gold:20}},
  blacksmith:{id:'blacksmith',name:'Iron for the Forge',description:'Recover five pieces of usable ore for the village smith.',objectives:[{id:'ore',type:'COLLECT',target:'iron-ore',label:'Collect Iron Ore',required:5},{id:'talk',type:'TALK',target:'blacksmith',label:'Speak to the blacksmith',required:1}],reward:{xp:100,gold:35}}
};
export function makeItem(id,qty=1){return {...ITEMS[id],qty,equipped:false};}
export function initialState(name='Kael',background='wanderer'){
 const b=BACKGROUNDS[background]||BACKGROUNDS.wanderer;
 const stats={might:3,agility:3,mind:2,will:2,endurance:3,perception:2,charisma:2,luck:2};
 if(background==='soldier') stats.might++;
 if(background==='scholar') stats.mind++;
 if(background==='thief') stats.agility++;
 return {version:SAVE_VERSION,campaignId:crypto.randomUUID?.()||String(Date.now()),turn:1,location:'Whispering Crossroads',scene:'A cracked road beneath a violet sky. The crossroads is too quiet.',player:{name:name||'Kael',background,level:1,xp:0,hp:28,maxHp:28,mp:12,maxMp:12,gold:25,stats,inventory:[{...ITEMS['rust-sword'],qty:1,equipped:true,slot:'mainHand'},{...ITEMS.moonleaf,qty:2,equipped:false}],equipment:{mainHand:'rust-sword',offHand:null,head:null,chest:null,legs:null,feet:null,ring1:null,ring2:null,amulet:null},talents:{ironWill:b.talents.ironWill||0,quickHands:b.talents.quickHands||0,arcaneEdge:b.talents.arcaneEdge||0},conditions:[],abilities:['strike','guard','fireball','firstAid']},world:{day:1,threat:0,weather:'violet dusk',flags:{},factions:{Wardens:b.reputation.Wardens||0,VeiledCourt:b.reputation.VeiledCourt||0,FreeMerchants:b.reputation.FreeMerchants||0},npcs:{},territories:{},rumors:[]},quests:{active:['crossroads'],completed:[],progress:{crossroads:{investigate:0,survive:0},blacksmith:{ore:0,talk:0}}},history:[],pending:null,ai:{memory:[],summary:''},meta:{createdAt:Date.now(),updatedAt:Date.now()}};
}