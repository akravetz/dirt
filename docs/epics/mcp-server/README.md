# Epic: MCP Server

Status: planning
Priority: medium
Created: 2026-03-22

## Goal

MCP server for Claude Desktop integration. Exposes the same data the web UI shows — latest screenshot, sensor readings, history — as MCP tools that Claude Desktop can call.

## Scope

- MCP server using the `mcp` Python SDK
- Tool: get latest webcam snapshot
- Tool: get current temperature and humidity
- Tool: get sensor history for a time range
- Tool: get grow status summary

## Acceptance Criteria

- MCP server starts alongside or independently of the web server
- Claude Desktop can connect and call all tools
- Tools return structured data that Claude can reason about
- Snapshot tool returns the image in a format Claude can display

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:mcp-server"`
