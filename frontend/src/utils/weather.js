export const REGIONS = ['울산', '거제', '목포']
export const REGION_KEY = 'swp_region'

export function weatherIcon(c = '') {
  if (c.includes('맑')) return '☀️'
  if (c.includes('구름')) return '⛅'
  if (c.includes('흐')) return '☁️'
  if (c.includes('눈')) return '❄️'
  if (c.includes('비')) return '🌧️'
  return '🌤️'
}
