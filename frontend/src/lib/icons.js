import {
  Wallet, CreditCard, Banknote, PiggyBank, Briefcase, Landmark, Coins,
  ShoppingCart, ShoppingBag, Home, Car, Bus, Fuel, Utensils, Coffee,
  Gift, Heart, Plane, Gamepad2, Book, GraduationCap, Stethoscope, Pill,
  Shirt, Baby, Dog, Dumbbell, Wifi, Phone, Smartphone, Zap, Droplet, Flame,
  Film, Music, Scissors, Wrench, TreePine, Sparkles, PawPrint, Cigarette,
  Cake, Wine, Bike, Train, Hotel, Palette, Camera, Cat,
  FileText, Receipt, Building2, HandCoins,
  Pizza, Beer, IceCreamCone, Apple, Carrot, Fish, Beef, Milk, Salad,
  Sandwich, Croissant, Donut, Popcorn, CupSoda, Martini, Candy,
  Truck, Ship, Footprints, Sailboat,
  Tv, Headphones, Laptop, Monitor, Printer,
  Sofa, BedDouble, Lamp, Bath, Refrigerator,
  Gem, Watch, Glasses, ShoppingBasket, Store, Package,
  Church, Syringe, Activity, HeartPulse, Thermometer, Ambulance,
  Hammer, Paintbrush, Ruler, Axe,
  Ticket, Tent, Mountain, Umbrella, Sun, Snowflake, Trees, Waves,
  Dices, Puzzle, Trophy, Medal, Target, Guitar, Mic,
  Flower, Sprout, Leaf,
  Pencil, Backpack, Calculator, Library, School,
  Bird, Rabbit, Egg, Star, Crown,
  HelpCircle, Plus
} from 'lucide-svelte'

export const iconRegistry = {
  wallet: Wallet, 'credit-card': CreditCard, banknote: Banknote,
  'piggy-bank': PiggyBank, briefcase: Briefcase, landmark: Landmark, coins: Coins,
  'shopping-cart': ShoppingCart, 'shopping-bag': ShoppingBag, home: Home,
  car: Car, bus: Bus, fuel: Fuel, utensils: Utensils, coffee: Coffee,
  gift: Gift, heart: Heart, plane: Plane, gamepad: Gamepad2, book: Book,
  'graduation-cap': GraduationCap, stethoscope: Stethoscope, pill: Pill,
  shirt: Shirt, baby: Baby, dog: Dog, dumbbell: Dumbbell, wifi: Wifi,
  phone: Phone, smartphone: Smartphone, zap: Zap, droplet: Droplet, flame: Flame,
  film: Film, music: Music, scissors: Scissors, wrench: Wrench, tree: TreePine,
  sparkles: Sparkles, paw: PawPrint, cigarette: Cigarette, cake: Cake,
  wine: Wine, bike: Bike, train: Train, hotel: Hotel, palette: Palette,
  camera: Camera, cat: Cat,
  'file-text': FileText, receipt: Receipt, building: Building2, 'hand-coins': HandCoins,
  pizza: Pizza, beer: Beer, 'ice-cream': IceCreamCone, apple: Apple, carrot: Carrot,
  fish: Fish, beef: Beef, milk: Milk, salad: Salad, sandwich: Sandwich,
  croissant: Croissant, donut: Donut, popcorn: Popcorn, soda: CupSoda,
  martini: Martini, candy: Candy,
  truck: Truck, ship: Ship, footprints: Footprints, sailboat: Sailboat,
  tv: Tv, headphones: Headphones, laptop: Laptop, monitor: Monitor, printer: Printer,
  sofa: Sofa, bed: BedDouble, lamp: Lamp, bath: Bath, fridge: Refrigerator,
  gem: Gem, watch: Watch, glasses: Glasses, basket: ShoppingBasket,
  store: Store, package: Package,
  church: Church, syringe: Syringe, activity: Activity, 'heart-pulse': HeartPulse,
  thermometer: Thermometer, ambulance: Ambulance,
  hammer: Hammer, paintbrush: Paintbrush, ruler: Ruler, axe: Axe,
  ticket: Ticket, tent: Tent, mountain: Mountain, umbrella: Umbrella,
  sun: Sun, snowflake: Snowflake, trees: Trees, waves: Waves,
  dices: Dices, puzzle: Puzzle, trophy: Trophy, medal: Medal, target: Target,
  guitar: Guitar, mic: Mic,
  flower: Flower, sprout: Sprout, leaf: Leaf,
  pencil: Pencil, backpack: Backpack, calculator: Calculator,
  library: Library, school: School,
  bird: Bird, rabbit: Rabbit, egg: Egg, star: Star, crown: Crown,
  'help-circle': HelpCircle
}

export function getIcon(name) {
  return iconRegistry[name] || HelpCircle
}

// Иконки для карточек категорий трат
export const CATEGORY_ICONS = [
  'shopping-cart', 'shopping-bag', 'basket', 'store', 'package',
  'utensils', 'coffee', 'pizza', 'beer', 'wine', 'martini', 'soda',
  'ice-cream', 'cake', 'donut', 'croissant', 'popcorn', 'candy', 'sandwich',
  'salad', 'apple', 'carrot', 'fish', 'beef', 'milk', 'egg',
  'home', 'sofa', 'bed', 'lamp', 'bath', 'fridge',
  'car', 'fuel', 'bus', 'train', 'plane', 'bike', 'truck', 'ship', 'sailboat', 'footprints',
  'shirt', 'glasses', 'watch', 'gem',
  'gift', 'heart', 'hotel', 'tent', 'mountain', 'umbrella', 'ticket',
  'gamepad', 'film', 'music', 'guitar', 'mic', 'dices', 'puzzle', 'trophy', 'medal', 'target',
  'book', 'graduation-cap', 'pencil', 'backpack', 'calculator', 'library', 'school',
  'stethoscope', 'pill', 'syringe', 'activity', 'heart-pulse', 'thermometer', 'ambulance', 'church',
  'baby', 'paw', 'dog', 'cat', 'bird', 'rabbit',
  'dumbbell', 'wifi', 'smartphone', 'phone', 'tv', 'headphones', 'laptop', 'monitor', 'printer',
  'zap', 'droplet', 'flame', 'sun', 'snowflake', 'waves',
  'scissors', 'wrench', 'hammer', 'paintbrush', 'ruler', 'axe',
  'cigarette', 'camera', 'palette', 'tree', 'trees', 'flower', 'sprout', 'leaf',
  'sparkles', 'star', 'crown', 'coins', 'receipt', 'file-text'
]

// Иконки для счетов
export const ACCOUNT_ICONS = [
  'wallet', 'credit-card', 'banknote', 'piggy-bank', 'briefcase',
  'landmark', 'coins', 'smartphone', 'sparkles', 'home'
]

// Иконки для долгов/кредитов/лизингов
export const DEBT_ICONS = [
  'landmark', 'credit-card', 'car', 'home', 'building', 'hand-coins',
  'file-text', 'receipt', 'coins', 'banknote', 'smartphone'
]

export const PALETTE = [
  // фиолетовые / синие
  '#6366f1', '#4f46e5', '#8b5cf6', '#7c3aed', '#a855f7', '#9333ea',
  '#3b82f6', '#2563eb', '#0ea5e9', '#0284c7',
  // розовые / красные
  '#d946ef', '#c026d3', '#ec4899', '#db2777', '#f43f5e', '#e11d48',
  '#ef4444', '#dc2626',
  // оранжевые / жёлтые
  '#f97316', '#ea580c', '#f59e0b', '#d97706', '#eab308', '#ca8a04',
  // зелёные / бирюзовые
  '#84cc16', '#65a30d', '#22c55e', '#16a34a', '#10b981', '#059669',
  '#14b8a6', '#0d9488', '#06b6d4', '#0891b2',
  // нейтральные
  '#78716c', '#64748b', '#475569', '#334155'
]
