export function formatPolygonPoints(points = []) {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

export function getSvgPoint(event, svgElement) {
  if (!svgElement) return null
  const rect = svgElement.getBoundingClientRect()
  if (!rect.width || !rect.height) return null

  const viewBox = svgElement.viewBox.baseVal
  const viewBoxWidth = viewBox?.width || rect.width
  const viewBoxHeight = viewBox?.height || rect.height
  const viewBoxX = viewBox?.x || 0
  const viewBoxY = viewBox?.y || 0

  return {
    x: viewBoxX + ((event.clientX - rect.left) / rect.width) * viewBoxWidth,
    y: viewBoxY + ((event.clientY - rect.top) / rect.height) * viewBoxHeight,
  }
}

export function polygonCentroid(points = []) {
  if (!points.length) return { x: 0, y: 0 }

  let signedArea = 0
  let centroidX = 0
  let centroidY = 0

  points.forEach((point, index) => {
    const next = points[(index + 1) % points.length]
    const cross = point.x * next.y - next.x * point.y
    signedArea += cross
    centroidX += (point.x + next.x) * cross
    centroidY += (point.y + next.y) * cross
  })

  signedArea *= 0.5
  if (Math.abs(signedArea) < 1e-9) {
    return {
      x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
      y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
    }
  }

  return {
    x: centroidX / (6 * signedArea),
    y: centroidY / (6 * signedArea),
  }
}
