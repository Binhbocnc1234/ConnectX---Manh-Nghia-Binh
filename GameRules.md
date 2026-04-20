# ConnectX Game Rules

## Objective

Get a certain number of your checkers in a row (horizontally, vertically, or diagonally) on the game board before your opponent. The default is **four-in-a-row**.

## How To Play

1. **Turn Order**: Player 1 takes the first turn
2. **Make a Move**: Drop one checker into a column at the top of the board
3. **Landing**: The checker lands in the last empty row of that column

### Game Outcomes

After dropping a checker, one of these occurs:

- **You Lose**: Column has no empty rows or is out of range
- **You Win**: Your checker creates an "X-in-a-row" (e.g., 4 in a row)
- **Tie**: No empty cells remain on the board
- **Continue**: Otherwise, it becomes your opponent's turn

## Agent Requirements

### Input Parameters

An Agent receives:

- **Board Configuration**:
  - Number of columns
  - Number of rows
  - Number of checkers needed in a row to win

- **Board State** (serialized grid):
  - `0` = Empty cell
  - `1` = Player 1's checker
  - `2` = Player 2's checker

- **Current Player**: `1` or `2`

### Output

Return the column where you want to drop a checker:
- **Format**: Integer in range `[0, columns)`
- **Direction**: Columns go left to right, rows go top to bottom